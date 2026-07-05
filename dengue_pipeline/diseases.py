from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiseaseConfig:
    name: str
    label: str
    years: tuple[int, ...]
    train_years: tuple[int, ...]
    validation_years: tuple[int, ...]
    test_years: tuple[int, ...]
    expected_split_rows: dict[str, int]


DISEASE_CONFIGS = {
    "dengue": DiseaseConfig(
        name="dengue",
        label="Dengue",
        years=tuple(range(2014, 2022)),
        train_years=(2017, 2018, 2019),
        validation_years=(2020,),
        test_years=(2021,),
        expected_split_rows={
            "train": 2_874_235,
            "validation": 1_331_664,
            "test": 940_304,
        },
    ),
    "chikungunya": DiseaseConfig(
        name="chikungunya",
        label="Chikungunya",
        years=tuple(range(2017, 2026)),
        train_years=tuple(range(2017, 2024)),
        validation_years=(2024,),
        test_years=(2025,),
        expected_split_rows={
            "train": 1_150_714,
            "validation": 393_413,
            "test": 235_703,
        },
    ),
}


def get_disease_config(disease: str) -> DiseaseConfig:
    normalized = disease.strip().lower()
    aliases = {
        "chikungunha": "chikungunya",
        "chik": "chikungunya",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        return DISEASE_CONFIGS[normalized]
    except KeyError as exc:
        raise ValueError(
            "disease must be 'dengue' or 'chikungunya'"
        ) from exc


def select_disease(dengue: int, chikungunya: int) -> str:
    if dengue not in (0, 1) or chikungunya not in (0, 1):
        raise ValueError("DENGUE and CHIKUNGUNYA must be 0 or 1")
    if dengue + chikungunya != 1:
        raise ValueError(
            "exactly one disease must be selected: "
            "DENGUE=1 or CHIKUNGUNYA=1"
        )
    return "dengue" if dengue else "chikungunya"


__all__ = [
    "DISEASE_CONFIGS",
    "DiseaseConfig",
    "get_disease_config",
    "select_disease",
]
