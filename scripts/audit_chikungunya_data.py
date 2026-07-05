from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dengue_pipeline.cleaner import REQUIRED_STANDARDIZED_COLUMNS  # noqa: E402
from dengue_pipeline.sinan_mappings import COLUMN_RENAME_MAP  # noqa: E402


DEFAULT_YEARS = tuple(range(2015, 2027))
DOWNLOAD_DIR = PROJECT_ROOT / "data" / "raw" / "downloads"
AUDIT_PATH = (
    PROJECT_ROOT / "reports" / "data" / "chikungunya_data_audit.csv"
)
FIELD_AUDIT_PATH = (
    PROJECT_ROOT / "reports" / "data" / "chikungunya_field_audit.csv"
)
SYMPTOM_AUDIT_PATH = (
    PROJECT_ROOT / "reports" / "data" / "chikungunya_symptom_audit.csv"
)

RAW_SYMPTOM_COLUMNS = (
    "FEBRE",
    "MIALGIA",
    "CEFALEIA",
    "EXANTEMA",
    "VOMITO",
    "NAUSEA",
    "DOR_COSTAS",
    "CONJUNTVIT",
    "ARTRITE",
    "ARTRALGIA",
    "PETEQUIA_N",
    "DOR_RETRO",
)

# In the older, chikungunya-specific export, 1/2 mean
# confirmed/discarded. In the combined dengue/chikungunya export, 13/5 mean
# chikungunya/discarded. The 2015-2016 files contain both conventions.
LEGACY_POSITIVE_CLASSIFICATIONS = frozenset({"1", "13"})
LEGACY_NEGATIVE_CLASSIFICATIONS = frozenset({"2", "5"})
MODERN_POSITIVE_CLASSIFICATIONS = frozenset({"13"})
MODERN_NEGATIVE_CLASSIFICATIONS = frozenset({"5"})


def parse_years(value: str | None) -> tuple[int, ...]:
    if not value:
        return DEFAULT_YEARS
    years = tuple(sorted({int(item.strip()) for item in value.split(",")}))
    unsupported = set(years) - set(DEFAULT_YEARS)
    if unsupported:
        raise argparse.ArgumentTypeError(
            f"unsupported chikungunya years: {sorted(unsupported)}"
        )
    return years


def required_raw_columns() -> list[str]:
    reverse = {
        standardized: raw
        for raw, standardized in COLUMN_RENAME_MAP.items()
    }
    missing = REQUIRED_STANDARDIZED_COLUMNS - set(reverse)
    if missing:
        raise RuntimeError(
            "Required standardized columns without SINAN mapping: "
            f"{sorted(missing)}"
        )
    return sorted(reverse[column] for column in REQUIRED_STANDARDIZED_COLUMNS)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while block := file.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def csv_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]
    if len(members) != 1:
        raise RuntimeError(
            f"Expected one CSV in {zip_path}, found {members}"
        )
    return members[0]


def inspect_header(zip_path: Path, member: str) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive, archive.open(member) as file:
        header = pd.read_csv(file, nrows=0, encoding="latin1")
    return [str(column).strip().upper() for column in header.columns]


def normalized_counts(values: pd.Series) -> Counter[str]:
    normalized = values.astype("string").fillna("").str.strip()
    normalized = normalized.replace({"<NA>": "", "nan": ""})
    return Counter(normalized.tolist())


def sorted_json(counter: Counter[str] | dict[str, int]) -> str:
    return json.dumps(
        dict(sorted(counter.items())),
        ensure_ascii=False,
        sort_keys=True,
    )


def classification_codes(
    year: int,
) -> tuple[frozenset[str], frozenset[str]]:
    if year <= 2016:
        return (
            LEGACY_POSITIVE_CLASSIFICATIONS,
            LEGACY_NEGATIVE_CLASSIFICATIONS,
        )
    return (
        MODERN_POSITIVE_CLASSIFICATIONS,
        MODERN_NEGATIVE_CLASSIFICATIONS,
    )


def audit_year(
    year: int,
    zip_path: Path,
    chunk_size: int,
    required_columns: list[str],
) -> tuple[dict, list[dict], list[dict]]:
    member = csv_member(zip_path)
    header = inspect_header(zip_path, member)
    header_set = set(header)
    missing_required = sorted(set(required_columns) - header_set)
    positives, negatives = classification_codes(year)
    selected = sorted(
        (
            set(required_columns)
            | {
                "CLASSI_FIN",
                "DT_NOTIFIC",
                "DT_SIN_PRI",
                "ID_AGRAVO",
                "NDUPLIC_N",
                "NU_ANO",
                "SEM_NOT",
            }
        )
        & header_set
    )

    raw_rows = 0
    labeled_before_duplicate_filter = 0
    eligible_rows = 0
    positive_rows = 0
    negative_rows = 0
    duplicate_flagged_rows = 0
    duplicate_flagged_labeled_rows = 0
    invalid_notification_dates = 0
    invalid_onset_dates = 0
    negative_notification_delays = 0
    over_90_day_notification_delays = 0
    notification_date_min: pd.Timestamp | None = None
    notification_date_max: pd.Timestamp | None = None
    rows_outside_source_calendar_year = 0
    rows_outside_source_epi_year = 0
    eligible_rows_outside_source_calendar_year = 0
    eligible_rows_outside_source_epi_year = 0

    class_counts: Counter[str] = Counter()
    disease_counts: Counter[str] = Counter()
    notification_year_counts: Counter[str] = Counter()
    notification_epi_year_counts: Counter[str] = Counter()
    duplicate_flag_counts: Counter[str] = Counter()
    missing_counts = Counter({column: 0 for column in required_columns})
    symptom_counts = {
        column: Counter({"yes": 0, "no": 0, "missing": 0, "invalid": 0})
        for column in RAW_SYMPTOM_COLUMNS
    }

    with zipfile.ZipFile(zip_path) as archive, archive.open(member) as file:
        chunks = pd.read_csv(
            file,
            usecols=selected,
            dtype="string",
            chunksize=chunk_size,
            encoding="latin1",
            low_memory=False,
        )
        for chunk in chunks:
            chunk.columns = chunk.columns.str.upper()
            raw_rows += len(chunk)

            class_values = chunk["CLASSI_FIN"].fillna("").str.strip()
            class_counts.update(class_values.tolist())
            positive_mask = class_values.isin(positives)
            negative_mask = class_values.isin(negatives)
            labeled_mask = positive_mask | negative_mask
            labeled_before_duplicate_filter += int(labeled_mask.sum())

            duplicate_values = (
                chunk["NDUPLIC_N"].fillna("").str.strip()
                if "NDUPLIC_N" in chunk
                else pd.Series("", index=chunk.index, dtype="string")
            )
            duplicate_flag_counts.update(duplicate_values.tolist())
            duplicate_mask = duplicate_values.eq("2")
            duplicate_flagged_rows += int(duplicate_mask.sum())
            duplicate_flagged_labeled_rows += int(
                (duplicate_mask & labeled_mask).sum()
            )

            eligible_mask = labeled_mask & ~duplicate_mask
            eligible_rows += int(eligible_mask.sum())
            positive_rows += int((positive_mask & ~duplicate_mask).sum())
            negative_rows += int((negative_mask & ~duplicate_mask).sum())

            disease_counts.update(normalized_counts(chunk["ID_AGRAVO"]))
            notification_year = (
                chunk["NU_ANO"].fillna("").str.strip()
            )
            notification_year_counts.update(notification_year.tolist())
            rows_outside_source_calendar_year += int(
                notification_year.ne(str(year)).sum()
            )
            eligible_rows_outside_source_calendar_year += int(
                (eligible_mask & notification_year.ne(str(year))).sum()
            )

            notification_epi_year = (
                chunk["SEM_NOT"]
                .fillna("")
                .str.strip()
                .str.extract(r"^(\d{4})", expand=False)
                .fillna("")
            )
            notification_epi_year_counts.update(
                notification_epi_year.tolist()
            )
            rows_outside_source_epi_year += int(
                notification_epi_year.ne(str(year)).sum()
            )
            eligible_rows_outside_source_epi_year += int(
                (eligible_mask & notification_epi_year.ne(str(year))).sum()
            )

            raw_notification_date = (
                chunk["DT_NOTIFIC"].fillna("").str.strip()
            )
            notification_date = pd.to_datetime(
                raw_notification_date,
                errors="coerce",
            )
            invalid_notification_dates += int(
                (
                    eligible_mask
                    & raw_notification_date.ne("")
                    & notification_date.isna()
                ).sum()
            )
            eligible_dates = notification_date.loc[
                eligible_mask & notification_date.notna()
            ]
            if not eligible_dates.empty:
                chunk_min = eligible_dates.min()
                chunk_max = eligible_dates.max()
                notification_date_min = (
                    chunk_min
                    if notification_date_min is None
                    else min(notification_date_min, chunk_min)
                )
                notification_date_max = (
                    chunk_max
                    if notification_date_max is None
                    else max(notification_date_max, chunk_max)
                )

            raw_onset_date = chunk["DT_SIN_PRI"].fillna("").str.strip()
            onset_date = pd.to_datetime(raw_onset_date, errors="coerce")
            invalid_onset_dates += int(
                (
                    eligible_mask
                    & raw_onset_date.ne("")
                    & onset_date.isna()
                ).sum()
            )
            delay = (notification_date - onset_date).dt.days
            negative_notification_delays += int(
                (eligible_mask & delay.lt(0)).sum()
            )
            over_90_day_notification_delays += int(
                (eligible_mask & delay.gt(90)).sum()
            )

            eligible = chunk.loc[eligible_mask]
            for column in required_columns:
                if column not in eligible:
                    missing_counts[column] += len(eligible)
                    continue
                values = eligible[column].fillna("").str.strip()
                missing_counts[column] += int(values.eq("").sum())

            for column in RAW_SYMPTOM_COLUMNS:
                if column not in eligible:
                    symptom_counts[column]["missing"] += len(eligible)
                    continue
                values = eligible[column].fillna("").str.strip()
                symptom_counts[column]["yes"] += int(values.eq("1").sum())
                symptom_counts[column]["no"] += int(
                    values.isin(["0", "2"]).sum()
                )
                symptom_counts[column]["missing"] += int(values.eq("").sum())
                symptom_counts[column]["invalid"] += int(
                    (~values.isin(["", "0", "1", "2"])).sum()
                )

    field_rows = []
    for raw_column in required_columns:
        missing = int(missing_counts[raw_column])
        field_rows.append(
            {
                "year": year,
                "raw_column": raw_column,
                "standardized_column": COLUMN_RENAME_MAP[raw_column],
                "eligible_rows": eligible_rows,
                "missing_rows": missing,
                "missing_pct": (
                    round(100 * missing / eligible_rows, 4)
                    if eligible_rows
                    else None
                ),
                "column_present": raw_column in header_set,
            }
        )

    symptom_rows = []
    for raw_column in RAW_SYMPTOM_COLUMNS:
        counts = symptom_counts[raw_column]
        reported = counts["yes"] + counts["no"]
        symptom_rows.append(
            {
                "year": year,
                "raw_column": raw_column,
                "standardized_column": COLUMN_RENAME_MAP[raw_column],
                "eligible_rows": eligible_rows,
                "yes_rows": counts["yes"],
                "no_rows": counts["no"],
                "missing_rows": counts["missing"],
                "invalid_rows": counts["invalid"],
                "reported_pct": (
                    round(100 * reported / eligible_rows, 4)
                    if eligible_rows
                    else None
                ),
                "yes_pct_among_reported": (
                    round(100 * counts["yes"] / reported, 4)
                    if reported
                    else None
                ),
            }
        )

    schema_fingerprint = hashlib.sha256(
        "\n".join(sorted(header_set)).encode("utf-8")
    ).hexdigest()
    audit_row = {
        "year": year,
        "source_url": (
            "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/"
            f"SINAN/Chikungunya/csv/CHIKBR{year % 100:02d}.csv.zip"
        ),
        "source_sha256": sha256(zip_path),
        "size_bytes": zip_path.stat().st_size,
        "csv_member": member,
        "raw_columns": len(header),
        "unique_raw_columns": len(header_set),
        "schema_fingerprint": schema_fingerprint,
        "missing_pipeline_columns": json.dumps(missing_required),
        "pipeline_schema_compatible": not missing_required,
        "raw_rows": raw_rows,
        "labeled_before_duplicate_filter": labeled_before_duplicate_filter,
        "duplicate_flagged_rows": duplicate_flagged_rows,
        "duplicate_flagged_labeled_rows": duplicate_flagged_labeled_rows,
        "eligible_rows": eligible_rows,
        "positive_rows": positive_rows,
        "negative_rows": negative_rows,
        "excluded_rows": raw_rows - eligible_rows,
        "positive_pct": (
            round(100 * positive_rows / eligible_rows, 4)
            if eligible_rows
            else None
        ),
        "class_counts": sorted_json(class_counts),
        "disease_code_counts": sorted_json(disease_counts),
        "duplicate_flag_counts": sorted_json(duplicate_flag_counts),
        "notification_year_counts": sorted_json(notification_year_counts),
        "notification_epi_year_counts": sorted_json(
            notification_epi_year_counts
        ),
        "rows_outside_source_calendar_year": (
            rows_outside_source_calendar_year
        ),
        "rows_outside_source_epi_year": rows_outside_source_epi_year,
        "eligible_rows_outside_source_calendar_year": (
            eligible_rows_outside_source_calendar_year
        ),
        "eligible_rows_outside_source_epi_year": (
            eligible_rows_outside_source_epi_year
        ),
        "notification_date_min": (
            notification_date_min.date().isoformat()
            if notification_date_min is not None
            else None
        ),
        "notification_date_max": (
            notification_date_max.date().isoformat()
            if notification_date_max is not None
            else None
        ),
        "invalid_notification_dates": invalid_notification_dates,
        "invalid_onset_dates": invalid_onset_dates,
        "negative_notification_delays": negative_notification_delays,
        "over_90_day_notification_delays": (
            over_90_day_notification_delays
        ),
    }
    return audit_row, field_rows, symptom_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the official annual SINAN chikungunya CSV ZIP files "
            "against the dengue preprocessing contract."
        )
    )
    parser.add_argument(
        "--years",
        help="Comma-separated years; defaults to 2015-2026.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100_000,
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=DOWNLOAD_DIR,
    )
    args = parser.parse_args()
    years = parse_years(args.years)
    if args.chunk_size < 10_000:
        parser.error("--chunk-size must be at least 10000")

    required_columns = required_raw_columns()
    audit_rows = []
    field_rows = []
    symptom_rows = []

    for year in years:
        zip_path = (
            args.download_dir / f"CHIKBR{year % 100:02d}.csv.zip"
        )
        if not zip_path.exists():
            raise FileNotFoundError(
                f"Missing {zip_path}; download the official CSV ZIP first."
            )
        audit, fields, symptoms = audit_year(
            year,
            zip_path,
            args.chunk_size,
            required_columns,
        )
        audit_rows.append(audit)
        field_rows.extend(fields)
        symptom_rows.extend(symptoms)
        print(
            f"[{year}] {audit['raw_rows']:,} raw / "
            f"{audit['eligible_rows']:,} eligible / "
            f"{audit['raw_columns']} columns",
            flush=True,
        )

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audit_rows).sort_values("year").to_csv(
        AUDIT_PATH,
        index=False,
        encoding="utf-8",
    )
    pd.DataFrame(field_rows).sort_values(
        ["year", "raw_column"]
    ).to_csv(
        FIELD_AUDIT_PATH,
        index=False,
        encoding="utf-8",
    )
    pd.DataFrame(symptom_rows).sort_values(
        ["year", "raw_column"]
    ).to_csv(
        SYMPTOM_AUDIT_PATH,
        index=False,
        encoding="utf-8",
    )
    print(f"Audit written to {AUDIT_PATH}")
    print(f"Field audit written to {FIELD_AUDIT_PATH}")
    print(f"Symptom audit written to {SYMPTOM_AUDIT_PATH}")


if __name__ == "__main__":
    main()
