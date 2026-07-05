from pathlib import Path

from .diseases import get_disease_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
RAW_DOWNLOAD_DIR = RAW_DATA_DIR / "downloads"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PROCESSED_ANALYSIS_DIR = PROCESSED_DATA_DIR / "analysis"
PROCESSED_ML_DIR = PROCESSED_DATA_DIR / "ml"

DOCS_DIR = PROJECT_ROOT / "docs"
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
MODEL_FIGURES_DIR = FIGURES_DIR / "modeling"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"

DENGUE_YEARS = tuple(range(2014, 2022))
# Treino restrito a 2017-2019: mesma definição de alvo que 2020/2021 e sintomas
# registrados (2014-2015 vêm ~sem sintoma; 2016 parcial). O ETL e os lookups
# continuam usando todos os anos de DENGUE_YEARS.
TRAIN_YEARS = (2017, 2018, 2019)
VALIDATION_YEARS = (2020,)
TEST_YEARS = (2021,)
EXPECTED_SPLIT_ROWS = {
    "train": 2_874_235,
    "validation": 1_331_664,
    "test": 940_304,
}


def disease_years(disease: str = "dengue") -> tuple[int, ...]:
    return get_disease_config(disease).years


def temporal_split(disease: str = "dengue") -> tuple[
    tuple[int, ...],
    tuple[int, ...],
    tuple[int, ...],
]:
    config = get_disease_config(disease)
    return (
        config.train_years,
        config.validation_years,
        config.test_years,
    )


def expected_split_rows(disease: str = "dengue") -> dict[str, int]:
    return get_disease_config(disease).expected_split_rows


def analysis_dataset_path(
    year: int,
    disease: str = "dengue",
) -> Path:
    disease = get_disease_config(disease).name
    return PROCESSED_ANALYSIS_DIR / f"{disease}_analysis_{year}.parquet"


def ml_dataset_path(year: int, disease: str = "dengue") -> Path:
    disease = get_disease_config(disease).name
    return PROCESSED_ML_DIR / f"{disease}_ml_{year}.parquet"


def disease_models_dir(disease: str = "dengue") -> Path:
    disease = get_disease_config(disease).name
    return MODELS_DIR if disease == "dengue" else MODELS_DIR / disease


def disease_model_figures_dir(disease: str = "dengue") -> Path:
    disease = get_disease_config(disease).name
    return (
        MODEL_FIGURES_DIR
        if disease == "dengue"
        else MODEL_FIGURES_DIR / disease
    )


def disease_model_manifest_path(disease: str = "dengue") -> Path:
    return disease_models_dir(disease) / "model_manifest.json"


def disease_ensemble_config_path(disease: str = "dengue") -> Path:
    return disease_models_dir(disease) / "ensemble_config.json"


def disease_local_density_lookup_path(
    disease: str = "dengue",
) -> Path:
    return disease_models_dir(disease) / "local_density_lookup.parquet"


def disease_local_positivity_lookup_path(
    disease: str = "dengue",
) -> Path:
    return disease_models_dir(disease) / "local_positivity_lookup.parquet"


SIMULATION_SOURCE_PARQUET = analysis_dataset_path(2021)
SIMULATION_POOL_PATH = PROCESSED_DATA_DIR / "dengue_simulation_pool.parquet"

MODEL_MANIFEST_PATH = MODELS_DIR / "model_manifest.json"
ENSEMBLE_CONFIG_PATH = MODELS_DIR / "ensemble_config.json"
LOCAL_DENSITY_LOOKUP_PATH = MODELS_DIR / "local_density_lookup.parquet"
LOCAL_POSITIVITY_LOOKUP_PATH = MODELS_DIR / "local_positivity_lookup.parquet"
