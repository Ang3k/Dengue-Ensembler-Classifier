from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .features import (
    DATASET_METADATA_COLUMNS,
    MODEL_FEATURE_COLUMNS,
)
from .paths import (
    TEST_YEARS,
    TRAIN_YEARS,
    VALIDATION_YEARS,
    ml_dataset_path,
    temporal_split,
)


def load_ml_years(
    years: Iterable[int],
    disease: str = "dengue",
) -> pd.DataFrame:
    frames = []
    for year in years:
        path = ml_dataset_path(int(year), disease)
        if not path.exists():
            raise FileNotFoundError(
                f"Processed dataset not found for {year}: {path}. "
                "Run the corresponding data preparation script first."
            )
        frames.append(pd.read_parquet(path))
    if not frames:
        raise ValueError("At least one dataset year is required")
    return pd.concat(frames, ignore_index=True)


def split_features_target(
    dataset: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    missing = (
        set(DATASET_METADATA_COLUMNS)
        | set(MODEL_FEATURE_COLUMNS)
    ) - set(dataset.columns)
    if missing:
        raise ValueError(f"Processed dataset columns missing: {sorted(missing)}")

    features = dataset.loc[:, MODEL_FEATURE_COLUMNS].astype("float32")
    target = dataset["final_classification"].astype("int8")
    return features, target


def load_temporal_splits(
    disease: str = "dengue",
) -> dict[str, pd.DataFrame]:
    if disease == "dengue":
        train_years = TRAIN_YEARS
        validation_years = VALIDATION_YEARS
        test_years = TEST_YEARS
    else:
        train_years, validation_years, test_years = temporal_split(disease)
    return {
        "train": load_ml_years(train_years, disease),
        "validation": load_ml_years(validation_years, disease),
        "test": load_ml_years(test_years, disease),
    }


__all__ = [
    "load_ml_years",
    "load_temporal_splits",
    "split_features_target",
]
