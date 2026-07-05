from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen
import zipfile

import pandas as pd
import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dengue_pipeline.cleaner import (  # noqa: E402
    ANALYSIS_COLUMNS,
    DengueDataCleaner,
    classification_counts,
)
from dengue_pipeline.diseases import get_disease_config  # noqa: E402
from dengue_pipeline.features import (  # noqa: E402
    FEATURE_SCHEMA_VERSION,
    MODEL_FEATURE_COLUMNS,
)
from dengue_pipeline.paths import (  # noqa: E402
    RAW_DOWNLOAD_DIR,
    analysis_dataset_path,
    ml_dataset_path,
)
from scripts.prepare_dengue_data import (  # noqa: E402
    ParquetChunkWriter,
    csv_member,
    inspect_header,
    required_raw_columns,
)


DISEASE = "chikungunya"
CONFIG = get_disease_config(DISEASE)
MANIFEST_PATH = PROJECT_ROOT / "data" / "chikungunya_manifest.json"
AUDIT_PATH = (
    PROJECT_ROOT / "reports" / "data" / "chikungunya_etl_audit.csv"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    schema_path = PROJECT_ROOT / "data" / manifest["schema_reference"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))["schema"]
    expected_schema = {
        "raw_required_columns": required_raw_columns(),
        "analysis_columns": list(ANALYSIS_COLUMNS),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "model_feature_columns": list(MODEL_FEATURE_COLUMNS),
    }
    if schema != expected_schema:
        raise RuntimeError(
            "Referenced schema differs from the implemented pipeline."
        )
    for year in CONFIG.years:
        resource = manifest.get("years", {}).get(str(year), {})
        if len(resource.get("sha256", "")) != 64:
            raise RuntimeError(f"Manifest SHA-256 is missing for {year}")
    return manifest


def parse_years(raw: str | None) -> tuple[int, ...]:
    if not raw:
        return CONFIG.years
    years = tuple(sorted({int(value) for value in raw.split(",")}))
    unsupported = set(years) - set(CONFIG.years)
    if unsupported:
        raise ValueError(f"Unsupported years: {sorted(unsupported)}")
    return years


def download_resource(
    year: int,
    resource: dict,
    force: bool,
) -> tuple[Path, str]:
    RAW_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = RAW_DOWNLOAD_DIR / f"CHIKBR{year % 100:02d}.csv.zip"
    expected_hash = resource["sha256"].lower()
    expected_size = int(resource["size_bytes"])

    if destination.exists() and not force:
        actual_hash = sha256_file(destination)
        if (
            destination.stat().st_size == expected_size
            and actual_hash == expected_hash
        ):
            return destination, actual_hash

    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    print(f"[{year}] downloading {resource['url']}", flush=True)
    with urlopen(resource["url"], timeout=180) as response, temporary.open(
        "wb"
    ) as output:
        while chunk := response.read(4 * 1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)

    actual_hash = digest.hexdigest()
    if downloaded != expected_size or actual_hash != expected_hash:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"[{year}] downloaded resource differs from the manifest"
        )
    temporary.replace(destination)
    return destination, actual_hash


def prepare_year(
    year: int,
    resource: dict,
    zip_path: Path,
    actual_hash: str,
    chunk_size: int,
) -> dict:
    member = csv_member(zip_path)
    header = inspect_header(zip_path, member)
    if len(header) != int(resource["raw_columns"]):
        raise RuntimeError(
            f"[{year}] column count mismatch: expected "
            f"{resource['raw_columns']}, received {len(header)}"
        )

    selected_columns = required_raw_columns()
    missing_raw = set(selected_columns) - set(header)
    if missing_raw:
        raise RuntimeError(
            f"[{year}] required raw columns missing: {sorted(missing_raw)}"
        )
    if "NDUPLIC_N" in header:
        selected_columns.append("NDUPLIC_N")

    analysis_writer = ParquetChunkWriter(
        analysis_dataset_path(year, DISEASE)
    )
    ml_writer = ParquetChunkWriter(ml_dataset_path(year, DISEASE))
    raw_rows = 0
    accepted_rows = 0
    positive_rows = 0
    negative_rows = 0
    class_counter: Counter[str] = Counter()
    symptom_missing: Counter[str] = Counter()
    process = psutil.Process()
    peak_rss_bytes = process.memory_info().rss

    try:
        with zipfile.ZipFile(zip_path) as archive, archive.open(member) as file:
            chunks = pd.read_csv(
                file,
                usecols=selected_columns,
                dtype="string",
                chunksize=chunk_size,
                encoding="latin1",
                low_memory=False,
            )
            for index, raw_chunk in enumerate(chunks, start=1):
                raw_chunk.columns = raw_chunk.columns.str.upper()
                raw_rows += len(raw_chunk)
                class_counter.update(
                    classification_counts(raw_chunk["CLASSI_FIN"])
                )

                analysis = DengueDataCleaner.transformar_analise_chunk(
                    raw_chunk,
                    year,
                    DISEASE,
                )
                accepted_rows += len(analysis)
                positive_rows += int(
                    analysis["final_classification"].eq(1).sum()
                )
                negative_rows += int(
                    analysis["final_classification"].eq(0).sum()
                )
                for symptom in (
                    "fever",
                    "myalgia",
                    "headache",
                    "rash",
                    "vomiting",
                    "nausea",
                    "back_pain",
                    "conjunctivitis",
                    "arthritis",
                    "joint_pain",
                    "petechiae",
                    "retro_orbital_pain",
                ):
                    symptom_missing[symptom] += int(
                        analysis[symptom].isna().sum()
                    )

                analysis_writer.write(analysis)
                ml_writer.write(
                    DengueDataCleaner.transformar_ml(analysis)
                )
                peak_rss_bytes = max(
                    peak_rss_bytes,
                    process.memory_info().rss,
                )
                print(
                    f"[{year}] chunk {index}: "
                    f"{raw_rows:,} raw / {accepted_rows:,} accepted",
                    flush=True,
                )

        expected_counts = {
            str(code): int(count)
            for code, count in resource["class_counts"].items()
        }
        if raw_rows != int(resource["raw_rows"]):
            raise RuntimeError(
                f"[{year}] raw row count mismatch: {raw_rows:,}"
            )
        if dict(sorted(class_counter.items())) != dict(
            sorted(expected_counts.items())
        ):
            raise RuntimeError(
                f"[{year}] CLASSI_FIN counts differ from the manifest"
            )
        expected_targets = {
            "accepted_rows": accepted_rows,
            "positive_rows": positive_rows,
            "negative_rows": negative_rows,
        }
        for field, actual in expected_targets.items():
            if actual != int(resource[field]):
                raise RuntimeError(
                    f"[{year}] {field} mismatch: "
                    f"{actual:,} != {int(resource[field]):,}"
                )

        analysis_writer.close()
        ml_writer.close()
    except Exception:
        analysis_writer.abort()
        ml_writer.abort()
        raise

    return {
        "year": year,
        "source_sha256": actual_hash,
        "raw_rows": raw_rows,
        "accepted_rows": accepted_rows,
        "positive_rows": positive_rows,
        "negative_rows": negative_rows,
        "removed_rows": raw_rows - accepted_rows,
        "peak_rss_gib": round(peak_rss_bytes / (1024**3), 3),
        "classification_counts": json.dumps(
            dict(sorted(class_counter.items())),
            ensure_ascii=True,
            sort_keys=True,
        ),
        "symptom_missing": json.dumps(
            dict(sorted(symptom_missing.items())),
            sort_keys=True,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare SINAN chikungunya data for 2017-2025."
    )
    parser.add_argument("--years")
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    years = parse_years(args.years)
    if args.chunk_size < 10_000:
        parser.error("--chunk-size must be at least 10000")

    manifest = load_manifest()
    audit_rows = []
    for year in years:
        resource = manifest["years"][str(year)]
        zip_path, actual_hash = download_resource(
            year,
            resource,
            args.force_download,
        )
        if not args.download_only:
            audit_rows.append(
                prepare_year(
                    year,
                    resource,
                    zip_path,
                    actual_hash,
                    args.chunk_size,
                )
            )

    if audit_rows:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        audit = pd.DataFrame(audit_rows)
        if AUDIT_PATH.exists():
            previous = pd.read_csv(AUDIT_PATH)
            previous = previous[
                ~previous["year"].isin(audit["year"])
            ]
            audit = pd.concat([previous, audit], ignore_index=True)
        audit.sort_values("year").to_csv(
            AUDIT_PATH,
            index=False,
            encoding="utf-8",
        )
        print(f"Audit written to {AUDIT_PATH}")


if __name__ == "__main__":
    main()
