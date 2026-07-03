from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from urllib.request import urlopen

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dengue_pipeline.paths import TRAIN_YEARS, analysis_dataset_path  # noqa: E402


MUNICIPALITIES_PATH = PROJECT_ROOT / "data" / "municipios.json"
HEALTH_REGIONS_PATH = PROJECT_ROOT / "data" / "regioes_saude.json"
HEALTH_REGIONS_URL = (
    "https://arquivosdadosabertos.saude.gov.br/dados/dbgeral/"
    "macroregiao_de_saude.json"
)


def load_official_health_regions(source_json: Path | None) -> list[dict]:
    if source_json is not None:
        payload = json.loads(source_json.read_text(encoding="utf-8"))
    else:
        with urlopen(HEALTH_REGIONS_URL, timeout=180) as response:
            payload = json.load(response)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("A referência oficial de regiões de saúde está vazia")
    return rows


def model_health_region_by_municipality() -> dict[int, int]:
    counts: Counter[tuple[int, int]] = Counter()
    for year in TRAIN_YEARS:
        path = analysis_dataset_path(year)
        if not path.exists():
            raise FileNotFoundError(
                f"Partição de análise ausente para {year}: {path}"
            )
        frame = pd.read_parquet(
            path,
            columns=[
                "residence_municipality",
                "residence_health_region",
            ],
        ).dropna()
        frame = frame[
            frame["residence_municipality"].gt(0)
            & frame["residence_health_region"].gt(0)
        ].astype("int64")
        counts.update(
            zip(
                frame["residence_municipality"],
                frame["residence_health_region"],
            )
        )

    selected: dict[int, tuple[int, int]] = {}
    for (municipality, region), count in counts.items():
        current = selected.get(municipality)
        if current is None or count > current[1]:
            selected[municipality] = (region, count)
    return {
        municipality: region
        for municipality, (region, _) in selected.items()
    }


def build_reference(official_rows: list[dict]) -> dict[str, list[dict]]:
    municipalities = json.loads(
        MUNICIPALITIES_PATH.read_text(encoding="utf-8")
    )
    ibge_by_sinan = {
        int(municipality["id"]) // 10: int(municipality["id"])
        for municipality in municipalities
    }
    official_by_sinan = {
        int(row["cod_municipio"]): row
        for row in official_rows
        if row.get("cod_municipio")
    }
    model_regions = model_health_region_by_municipality()

    reference: dict[str, list[dict]] = {}
    for sinan_code, model_region_code in sorted(model_regions.items()):
        ibge_code = ibge_by_sinan.get(sinan_code)
        official = official_by_sinan.get(sinan_code)
        if ibge_code is None or official is None:
            continue
        reference[str(ibge_code)] = [
            {
                "code": model_region_code,
                "name": str(official["regiao_de_saude"]),
                "state": str(official["sg_uf"]),
                "officialCode": int(official["cod_regiao_de_saude"]),
            }
        ]
    return reference


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Gera a referência município/região usada pela triagem. Os nomes "
            "vêm do OpenDataSUS e os códigos são os IDs internos presentes no "
            "período de treino do SINAN."
        )
    )
    parser.add_argument(
        "--source-json",
        type=Path,
        help="JSON já baixado do OpenDataSUS; por padrão faz o download.",
    )
    args = parser.parse_args()

    if not MUNICIPALITIES_PATH.exists():
        raise FileNotFoundError(
            f"Referência de municípios ausente: {MUNICIPALITIES_PATH}"
        )

    official_rows = load_official_health_regions(args.source_json)
    reference = build_reference(official_rows)
    if not reference:
        raise RuntimeError("Nenhuma referência município/região foi gerada")

    temporary = HEALTH_REGIONS_PATH.with_suffix(".json.part")
    temporary.write_text(
        json.dumps(reference, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(HEALTH_REGIONS_PATH)
    print(
        f"{len(reference):,} municípios gravados em {HEALTH_REGIONS_PATH}",
        flush=True,
    )


if __name__ == "__main__":
    main()
