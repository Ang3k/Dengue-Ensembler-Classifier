"""
API de predição de dengue e chikungunya.

Rode com:
    .venv\Scripts\python -m uvicorn api:app --reload

Treino e inferência usam o mesmo construtor de features sem estado. Todo
pré-processamento aprendido fica dentro do artefato de cada modelo e é ajustado
somente nos anos de treino.
"""

from datetime import date, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Literal
import unicodedata

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from dengue_pipeline.features import (
    FEATURE_SCHEMA_VERSION,
    MODEL_FEATURE_COLUMNS,
    SYMPTOM_COLUMNS,
    build_model_features,
    compute_local_density,
    compute_local_positivity,
)
from dengue_pipeline.diseases import DISEASE_CONFIGS, get_disease_config
from dengue_pipeline.paths import (
    SIMULATION_POOL_PATH,
    SIMULATION_SOURCE_PARQUET,
    disease_ensemble_config_path,
    disease_local_density_lookup_path,
    disease_local_positivity_lookup_path,
    disease_model_manifest_path,
    disease_models_dir,
)
from dengue_pipeline.sinan_mappings import (
    DENGUE_CLASSIFICATION_LABELS,
    EDUCATION_LABELS,
    PREGNANCY_LABELS,
    SEX_LABELS,
    RACE_LABELS,
    UF_ABBR_LABELS,
    UF_LABELS,
)
from dengue_pipeline.cbo_map import CBO_MAP
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Carregar modelos e o pré-processamento salvos
# ---------------------------------------------------------------------------
MODELOS_DISPONIVEIS = {
    "mlp":                 "mlp.joblib",
    "xgboost":             "xgboost.joblib",
    "lightgbm":            "lightgbm.joblib",
}
def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        logger.exception("Não foi possível carregar %s", path)
        return {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_model_bundle(disease: str) -> dict:
    config = get_disease_config(disease)
    models_dir = disease_models_dir(config.name)
    manifest_path = disease_model_manifest_path(config.name)
    ensemble_path = disease_ensemble_config_path(config.name)
    context_paths = {
        "local_density": disease_local_density_lookup_path(config.name),
        "local_positivity": disease_local_positivity_lookup_path(config.name),
    }
    manifest = _load_json(manifest_path)
    ensemble = _load_json(ensemble_path)
    try:
        weights = {
            str(name): float(weight)
            for name, weight in ensemble.get("weights", {}).items()
        }
        threshold = float(ensemble.get("threshold", 0.5))
        ensemble_values_valid = (
            set(weights) == set(MODELOS_DISPONIVEIS)
            and all(
                np.isfinite(weight) and weight > 0
                for weight in weights.values()
            )
            and np.isfinite(threshold)
            and 0 <= threshold <= 1
        )
    except (AttributeError, TypeError, ValueError):
        weights = {}
        threshold = 0.5
        ensemble_values_valid = False

    manifest_compatible = (
        manifest.get("disease", "dengue") == config.name
        and manifest.get("feature_schema_version")
        == FEATURE_SCHEMA_VERSION
        and manifest.get("feature_columns") == list(MODEL_FEATURE_COLUMNS)
        and manifest.get("periods", {}).get("train")
        == list(config.train_years)
        and manifest.get("periods", {}).get("validation")
        == list(config.validation_years)
        and manifest.get("periods", {}).get("test")
        == list(config.test_years)
        and manifest.get("row_counts") == config.expected_split_rows
    )
    lookups_compatible = all(
        path.exists()
        and manifest.get("context_lookups", {}).get(name, {}).get("file")
        == path.name
        and manifest.get("context_lookups", {}).get(name, {}).get("sha256")
        == _sha256_file(path)
        for name, path in context_paths.items()
    )
    ensemble_compatible = (
        ensemble.get("disease", "dengue") == config.name
        and ensemble.get("feature_schema_version") == FEATURE_SCHEMA_VERSION
        and ensemble.get("selection_period")
        == list(config.validation_years)
        and ensemble.get("test_period") == list(config.test_years)
        and set(ensemble.get("weights", {})) == set(MODELOS_DISPONIVEIS)
        and ensemble_values_valid
        and manifest_path.exists()
        and ensemble.get("model_manifest_sha256")
        == _sha256_file(manifest_path)
    )
    artifact_compatible = (
        manifest_compatible
        and lookups_compatible
        and ensemble_compatible
    )

    loaded_models = {}
    loading_errors = {}
    for name, filename in MODELOS_DISPONIVEIS.items():
        path = models_dir / filename
        if not artifact_compatible:
            loading_errors[name] = (
                "manifesto ausente ou incompatível com o esquema de "
                f"features {FEATURE_SCHEMA_VERSION}"
            )
            continue
        if not path.exists():
            loading_errors[name] = f"arquivo não encontrado: {path}"
            continue
        try:
            entry = manifest.get("models", {}).get(name, {})
            if entry.get("file") != filename:
                raise ValueError("arquivo difere do manifesto do modelo")
            if entry.get("sha256") != _sha256_file(path):
                raise ValueError("SHA-256 difere do manifesto do modelo")
            model = joblib.load(path)
            if name == "xgboost":
                internal_model = getattr(model, "model", None)
                if hasattr(internal_model, "set_params"):
                    internal_model.set_params(
                        device=os.getenv("XGBOOST_DEVICE", "cpu")
                    )
            elif name == "mlp" and hasattr(model, "device"):
                model.device = os.getenv("MLP_DEVICE", "auto")
            feature_names = list(
                getattr(model, "feature_names", None)
                or getattr(model, "feature_names_in_", [])
            )
            if feature_names != list(MODEL_FEATURE_COLUMNS):
                raise ValueError(
                    "features do modelo diferem de MODEL_FEATURE_COLUMNS"
                )
            loaded_models[name] = model
        except Exception as exc:
            loading_errors[name] = str(exc)
            logger.exception(
                "Não foi possível carregar o modelo %s de %s",
                name,
                config.name,
            )

    return {
        "config": config,
        "manifest": manifest,
        "ensemble": ensemble,
        "weights": weights,
        "threshold": threshold,
        "models": loaded_models,
        "loading_errors": loading_errors,
        "context_paths": context_paths,
        "manifest_compatible": manifest_compatible,
        "lookups_compatible": lookups_compatible,
        "ensemble_compatible": ensemble_compatible,
        "artifact_compatible": artifact_compatible,
    }


MODEL_BUNDLES = {
    disease: _load_model_bundle(disease)
    for disease in DISEASE_CONFIGS
}

# Aliases mantidos para compatibilidade com o cliente e os testes de dengue.
_dengue_bundle = MODEL_BUNDLES["dengue"]
model_manifest = _dengue_bundle["manifest"]
ensemble_config = _dengue_bundle["ensemble"]
ENSEMBLE_WEIGHTS = _dengue_bundle["weights"]
ENSEMBLE_THRESHOLD = _dengue_bundle["threshold"]
model_manifest_compatible = _dengue_bundle["manifest_compatible"]
context_lookups_compatible = _dengue_bundle["lookups_compatible"]
ensemble_config_compatible = _dengue_bundle["ensemble_compatible"]
artifact_set_compatible = _dengue_bundle["artifact_compatible"]
modelos = _dengue_bundle["models"]
erros_carregamento = _dengue_bundle["loading_errors"]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="API Arboviroses", version="1.1.0")

origens_cors = [
    origem.strip()
    for origem in os.getenv(
        "DENGUE_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origem.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_cors,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Schema de entrada — campos que o frontend já envia
# ---------------------------------------------------------------------------

def _ano_semana_epidemiologica(dia: date) -> tuple[int, int]:
    """Semana epidemiológica (convenção MMWR/SINAN: semana começa no domingo,
    a semana 1 é a que contém a maioria — a quarta-feira — no ano novo).

    Validado contra o SINAN real (100% de concordância). Necessário porque a
    densidade/positividade locais dependem da semana da notificação, e o
    frontend envia a data, não a semana.
    """
    wday = (dia.weekday() + 1) % 7  # domingo = 0
    quarta = dia + timedelta(days=(3 - wday))  # quarta-feira da semana epi
    ano = quarta.year
    jan1 = date(ano, 1, 1)
    jan1_wday = (jan1.weekday() + 1) % 7
    primeira_quarta = jan1 + timedelta(days=(3 - jan1_wday) % 7)
    semana = (quarta - primeira_quarta).days // 7 + 1
    return ano, semana


def _semana_epidemiologica(dia: date) -> int:
    return _ano_semana_epidemiologica(dia)[1]


class DadosPaciente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disease: Literal["dengue", "chikungunya"] = "dengue"

    # Paciente
    age_years: float | None = Field(default=None, ge=0, le=130)
    sex: Literal["M", "F", "I"] | None = None
    pregnancy_status: Literal[1, 2, 3, 4, 5, 6, 9] | None = None
    race: Literal[1, 2, 3, 4, 5, 9] | None = None
    education_level: int | None = Field(default=None, ge=0, le=10)
    occupation_code: str | None = Field(
        default=None,
        pattern=r"^(?:0|\d{5,6})$",
    )

    # Residência
    residence_state: int | None = None
    residence_municipality: int | None = Field(default=None, ge=0)
    residence_health_region: int | None = Field(default=None, ge=0)

    # Notificação / datas
    notification_date: date | None = None
    notification_year: int | None = Field(default=None, ge=1900, le=2100)
    notification_month: int | None = Field(default=None, ge=1, le=12)
    notification_epi_week: int | None = Field(default=None, ge=1)
    notif_municipality: int | None = Field(default=None, ge=0)
    notif_health_region: int | None = Field(default=None, ge=0)
    health_facility: int | None = Field(default=None, ge=0)

    # Início dos sintomas
    symptom_onset_date: date | None = None
    days_to_notification: float | None = Field(default=None, ge=0, le=90)
    symptom_epi_year: int | None = Field(default=None, ge=1900, le=2100)
    symptom_epi_week_number: int | None = Field(default=None, ge=1, le=53)

    # Sintomas (1 = sim, 0 = não)
    fever: int | None = Field(default=None, ge=0, le=1)
    myalgia: int | None = Field(default=None, ge=0, le=1)
    headache: int | None = Field(default=None, ge=0, le=1)
    rash: int | None = Field(default=None, ge=0, le=1)
    vomiting: int | None = Field(default=None, ge=0, le=1)
    nausea: int | None = Field(default=None, ge=0, le=1)
    back_pain: int | None = Field(default=None, ge=0, le=1)
    conjunctivitis: int | None = Field(default=None, ge=0, le=1)
    arthritis: int | None = Field(default=None, ge=0, le=1)
    joint_pain: int | None = Field(default=None, ge=0, le=1)
    petechiae: int | None = Field(default=None, ge=0, le=1)
    retro_orbital_pain: int | None = Field(default=None, ge=0, le=1)

    # Hospitalização
    hospitalized: Literal[1, 2, 9] | None = None
    hospital_state: int | None = None

    @field_validator("residence_state", "hospital_state")
    @classmethod
    def validar_uf(cls, valor):
        ufs = {
            11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27,
            28, 29, 31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53,
        }
        if valor is not None and valor not in ufs:
            raise ValueError("use um código IBGE de UF válido")
        return valor

    @field_validator("residence_municipality", mode="before")
    @classmethod
    def normalizar_codigo_municipio(cls, valor):
        if valor is None:
            return None
        try:
            codigo = int(valor)
        except (TypeError, ValueError):
            return valor
        # A API do IBGE usa sete dígitos (com dígito verificador), enquanto os
        # extratos do SINAN e os modelos usam os seis primeiros.
        return codigo // 10 if 1_000_000 <= codigo <= 9_999_999 else codigo

    @model_validator(mode="after")
    def validar_datas(self):
        if (
            self.notification_date
            and self.symptom_onset_date
            and self.notification_date < self.symptom_onset_date
        ):
            raise ValueError(
                "a notificação não pode ser anterior ao início dos sintomas"
            )
        return self

    @model_validator(mode="after")
    def derivar_semana_epi(self):
        # A semana da notificação alimenta o lookup de densidade/positividade
        # local. Se o cliente não a enviou mas mandou a data, deriva-a — senão
        # as duas features mais fortes do modelo ficariam NaN.
        if self.notification_epi_week is None and self.notification_date is not None:
            self.notification_epi_week = _semana_epidemiologica(
                self.notification_date
            )
        if self.notification_year is None and self.notification_date is not None:
            self.notification_year = self.notification_date.year
        if self.symptom_onset_date is not None:
            ano, semana = _ano_semana_epidemiologica(self.symptom_onset_date)
            if self.symptom_epi_week_number is None:
                self.symptom_epi_week_number = semana
            if self.symptom_epi_year is None:
                self.symptom_epi_year = ano
        return self


class SimulacaoRandomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Pré-processamento — replica o transformar_ml() do cleaner
# ---------------------------------------------------------------------------

SINTOMAS = list(SYMPTOM_COLUMNS)

# Código SINAN da escolaridade (0-10) -> ordinal usado no treino.
# Vem da composição EDUCATION_LABELS (código -> texto) com o map_escolaridade do
# cleaner (texto -> 0..5). Ex.: 0 = Analfabeto -> 1; 9/10 = Ignorado/NA -> 0.
SIMULATION_YEAR = 2021
SIMULATION_NOTIFICATION_MONTH_MIN = 1
SIMULATION_VALID_CLASSIFICATIONS = frozenset(DENGUE_CLASSIFICATION_LABELS)
MAX_SAMPLE_ATTEMPTS = 10

SIMULATION_SOURCE_COLUMNS = (
    "age_years",
    "sex",
    "pregnancy_status",
    "race",
    "education_level",
    "occupation_code",
    "residence_state",
    "residence_municipality",
    "residence_health_region",
    "notification_date",
    "notification_year",
    "notification_epi_week",
    "notif_municipality",
    "notif_health_region",
    "health_facility",
    "symptom_onset_date",
    "days_to_notification",
    "symptom_epi_year",
    "symptom_epi_week_number",
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
    "hospitalized",
    "hospital_state",
    "final_classification_code",
)
SIMULATION_DERIVED_COLUMNS = (
    "occupation_name",
    "final_classification_label",
)
# Features de contexto epidemiológico calculadas sobre 2021 e guardadas no pool,
# para a simulação usar o valor EXATO que o modelo viu no teste (não o lookup).
SIMULATION_CONTEXT_COLUMNS = (
    "local_density",
    "local_positivity",
)
SIMULATION_POOL_COLUMNS = (
    *SIMULATION_SOURCE_COLUMNS,
    *SIMULATION_DERIVED_COLUMNS,
    *SIMULATION_CONTEXT_COLUMNS,
)

SIMULATION_SYMPTOM_LABELS = {
    "fever": "Febre",
    "myalgia": "Mialgia",
    "headache": "Cefaleia",
    "rash": "Exantema",
    "vomiting": "Vomito",
    "nausea": "Nausea",
    "back_pain": "Dor nas costas",
    "conjunctivitis": "Conjuntivite",
    "arthritis": "Artrite",
    "joint_pain": "Dor nas articulacoes",
    "petechiae": "Petequias",
    "retro_orbital_pain": "Dor retro-orbital",
}

_simulation_pool: pd.DataFrame | None = None
_simulation_pool_lock = Lock()


def _carregar_lookup(path: Path, coluna: str) -> dict[tuple[int, int], float]:
    """Lê um artefato (município, semana-do-ano) -> valor típico.

    Features de contexto epidemiológico não são deriváveis de uma notificação
    isolada, então são consultadas aqui. Ausência do artefato ou da chave ->
    NaN, e os modelos de árvore lidam nativamente.
    """
    if not path.exists():
        return {}
    try:
        frame = pd.read_parquet(path)
        return {
            (int(row.residence_municipality), int(row.epi_week_of_year)): float(
                getattr(row, coluna)
            )
            for row in frame.itertuples(index=False)
        }
    except Exception:
        logger.exception("Não foi possível carregar %s", path)
        return {}


for _bundle in MODEL_BUNDLES.values():
    _paths = _bundle["context_paths"]
    _bundle["local_density_lookup"] = (
        _carregar_lookup(_paths["local_density"], "local_density")
        if _bundle["lookups_compatible"]
        else {}
    )
    _bundle["local_positivity_lookup"] = (
        _carregar_lookup(_paths["local_positivity"], "local_positivity")
        if _bundle["lookups_compatible"]
        else {}
    )

LOCAL_DENSITY_LOOKUP = _dengue_bundle["local_density_lookup"]
LOCAL_POSITIVITY_LOOKUP = _dengue_bundle["local_positivity_lookup"]


def _consultar_local(
    dados: DadosPaciente, lookup: dict[tuple[int, int], float]
) -> list[float] | None:
    municipio = dados.residence_municipality
    semana = dados.notification_epi_week
    if municipio is None or semana is None:
        return None
    valor = lookup.get((int(municipio), int(semana) % 100))
    return None if valor is None else [valor]


def construir_features(
    dados: DadosPaciente,
    local_density: list[float] | None = None,
    local_positivity: list[float] | None = None,
) -> pd.DataFrame:
    """Build one inference row with the shared training feature schema.

    Se ``local_density``/``local_positivity`` forem passados (caso histórico da
    simulação, com o valor exato de 2021), usa-os; senão consulta o lookup
    (paciente novo do /predict).
    """
    bundle = MODEL_BUNDLES[dados.disease]
    if local_density is None:
        local_density = _consultar_local(
            dados,
            bundle["local_density_lookup"],
        )
    if local_positivity is None:
        local_positivity = _consultar_local(
            dados,
            bundle["local_positivity_lookup"],
        )
    return build_model_features(
        pd.DataFrame([dados.model_dump(exclude={"disease"})]),
        local_density=local_density,
        local_positivity=local_positivity,
    )


def _colunas_esperadas(modelo):
    if hasattr(modelo, "feature_names_in_"):
        return list(modelo.feature_names_in_)
    nomes = getattr(modelo, "feature_names", None)
    return list(nomes) if nomes else None


def alinhar_colunas(df: pd.DataFrame, modelo):
    """Alinha as colunas com o que o modelo espera. Se faltar alguma coluna que
    o modelo precisa, devolve None + a lista de faltantes (em vez de preencher
    com 0 em silêncio), para o /predict pular esse modelo e avisar."""
    esperadas = _colunas_esperadas(modelo)
    if esperadas is None:
        return df, []
    faltantes = [c for c in esperadas if c not in df.columns]
    if faltantes:
        return None, faltantes
    return df[esperadas].astype("float32"), []


def _inferir_modelos(
    df: pd.DataFrame,
    disease: str = "dengue",
):
    """Executa a inferência em todos os modelos carregados para um vetor de
    features já construído."""
    disease = get_disease_config(disease).name
    bundle = MODEL_BUNDLES[disease]
    active_models = modelos if disease == "dengue" else bundle["models"]
    weights = (
        ENSEMBLE_WEIGHTS
        if disease == "dengue"
        else bundle["weights"]
    )
    threshold = (
        ENSEMBLE_THRESHOLD
        if disease == "dengue"
        else bundle["threshold"]
    )
    resultados = []
    ignorados = []
    probabilidades = {}

    for nome, modelo in active_models.items():
        df_alinhado, faltantes = alinhar_colunas(df.copy(), modelo)
        if df_alinhado is None:
            ignorados.append(
                {
                    "name": nome,
                    "reason": "features ausentes",
                    "missing": faltantes,
                }
            )
            continue

        try:
            proba = np.asarray(modelo.predict_proba(df_alinhado))
            if proba.ndim == 2 and proba.shape[1] >= 2:
                prob = float(proba[0, 1])
            elif proba.size:
                prob = float(proba.reshape(-1)[0])
            else:
                raise ValueError("predict_proba retornou um array vazio")
            if not np.isfinite(prob) or not 0 <= prob <= 1:
                raise ValueError(f"probabilidade inválida: {prob}")
            probabilidades[nome] = prob
            resultados.append(
                {
                    "name": nome,
                    "probability": round(prob * 100, 1),
                }
            )
        except Exception as exc:
            logger.exception("Falha ao executar o modelo %s", nome)
            ignorados.append(
                {
                    "name": nome,
                    "reason": str(exc),
                }
            )

    if not resultados:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Nenhum modelo conseguiu gerar uma predição",
                "ignored": ignorados,
            },
        )

    pesos_disponiveis = {
        name: weights[name]
        for name in probabilidades
        if name in weights
    }
    if set(pesos_disponiveis) != set(probabilidades):
        raise HTTPException(
            status_code=503,
            detail="A configuração do ensemble não corresponde aos modelos carregados.",
        )

    total_pesos = sum(pesos_disponiveis.values())
    pesos_normalizados = {
        name: weight / total_pesos
        for name, weight in pesos_disponiveis.items()
    }
    for resultado in resultados:
        resultado["weight"] = round(
            pesos_normalizados[resultado["name"]] * 100,
            1,
        )

    score_ponderado = float(
        sum(
            probabilidades[name] * pesos_normalizados[name]
            for name in probabilidades
        )
    )
    score_percentual = round(score_ponderado * 100, 1)
    threshold_percentual = round(float(threshold) * 100, 1)
    is_positive = score_ponderado >= float(threshold)
    return {
        "disease": disease,
        "models": resultados,
        "average": score_percentual,
        "threshold": threshold_percentual,
        "weighting": "recall",
        "isPositive": is_positive,
        "isDengue": disease == "dengue" and is_positive,
        "isChikungunya": disease == "chikungunya" and is_positive,
        "ignored": ignorados,
    }


def _exigir_conjunto_completo_de_modelos(
    disease: str = "dengue",
) -> None:
    disease = get_disease_config(disease).name
    bundle = MODEL_BUNDLES[disease]
    active_models = modelos if disease == "dengue" else bundle["models"]
    ausentes = [
        nome for nome in MODELOS_DISPONIVEIS if nome not in active_models
    ]
    if ausentes:
        raise HTTPException(
            status_code=503,
            detail={
                "message": (
                    "Nem todos os modelos necessários foram carregados "
                    f"para {disease}"
                ),
                "missing": ausentes,
            },
        )


def _to_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _one_of(value: Any, allowed: set[int]) -> int | None:
    parsed = _to_int(value)
    if parsed in allowed:
        return parsed
    return None


def _parse_age_years(encoded_age: Any) -> float | None:
    age = _to_int(encoded_age)
    if age is None:
        return None

    # SINAN usa unidade + quantidade no formato UYYY (ex.: 4025 = 25 anos).
    text = str(age).zfill(4)
    unit = int(text[0])
    value = int(text[1:])

    if unit == 4:
        years = float(value)
    elif unit == 3:
        years = float(value) / 12
    elif unit == 2:
        years = float(value) / 365
    elif unit == 1:
        years = float(value) / 8760
    else:
        years = float(age) if 0 <= age <= 130 else None

    if years is None or years < 0 or years > 130:
        return None
    return years


def _to_date(value: Any) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _to_occupation_code(value: Any) -> str | None:
    code = _to_int(value)
    if code is None or code < 0:
        return None
    code_text = str(code)
    return code_text if code == 0 or len(code_text) in (5, 6) else None


def _flag_from_sinan(value: Any) -> int | None:
    parsed = _to_int(value)
    if parsed == 1:
        return 1
    if parsed in {0, 2}:
        return 0
    return None


def _build_patient_from_sample(row: pd.Series) -> DadosPaciente:
    notification_date = _to_date(row.get("notification_date"))
    symptom_onset_date = _to_date(row.get("symptom_onset_date"))

    return DadosPaciente(
        age_years=(
            float(row.get("age_years"))
            if pd.notna(row.get("age_years"))
            else None
        ),
        sex=row.get("sex") if row.get("sex") in {"M", "F", "I"} else None,
        pregnancy_status=_one_of(row.get("pregnancy_status"), {1, 2, 3, 4, 5, 6, 9}),
        race=_one_of(row.get("race"), {1, 2, 3, 4, 5, 9}),
        education_level=_to_int(row.get("education_level")),
        occupation_code=_to_occupation_code(row.get("occupation_code")),
        residence_state=_to_int(row.get("residence_state")),
        residence_municipality=_to_int(row.get("residence_municipality")),
        residence_health_region=_to_int(row.get("residence_health_region")),
        notification_date=notification_date,
        notification_year=(notification_date.year if notification_date else None),
        notification_month=(notification_date.month if notification_date else None),
        notification_epi_week=_to_int(row.get("notification_epi_week")),
        notif_municipality=_to_int(row.get("notif_municipality")),
        notif_health_region=_to_int(row.get("notif_health_region")),
        health_facility=_to_int(row.get("health_facility")),
        symptom_onset_date=symptom_onset_date,
        days_to_notification=_to_int(row.get("days_to_notification")),
        symptom_epi_year=_to_int(row.get("symptom_epi_year")),
        symptom_epi_week_number=_to_int(
            row.get("symptom_epi_week_number")
        ),
        fever=_flag_from_sinan(row.get("fever")),
        myalgia=_flag_from_sinan(row.get("myalgia")),
        headache=_flag_from_sinan(row.get("headache")),
        rash=_flag_from_sinan(row.get("rash")),
        vomiting=_flag_from_sinan(row.get("vomiting")),
        nausea=_flag_from_sinan(row.get("nausea")),
        back_pain=_flag_from_sinan(row.get("back_pain")),
        conjunctivitis=_flag_from_sinan(row.get("conjunctivitis")),
        arthritis=_flag_from_sinan(row.get("arthritis")),
        joint_pain=_flag_from_sinan(row.get("joint_pain")),
        petechiae=_flag_from_sinan(row.get("petechiae")),
        retro_orbital_pain=_flag_from_sinan(row.get("retro_orbital_pain")),
        hospitalized=_one_of(row.get("hospitalized"), {1, 2, 9}),
        hospital_state=_to_int(row.get("hospital_state")),
    )


def _anonymized_case_from_sample(row: pd.Series, patient: DadosPaciente) -> dict[str, Any]:
    symptom_labels = [
        label
        for key, label in SIMULATION_SYMPTOM_LABELS.items()
        if getattr(patient, key, 0) == 1
    ]

    age = int(round(patient.age_years)) if patient.age_years is not None else None
    state_code = _to_int(row.get("residence_state"))
    municipality_code = _to_int(row.get("residence_municipality"))
    municipality = _MUNICIPIOS_BY_SINAN_CODE.get(municipality_code)
    occupation_name = row.get("occupation_name")

    return {
        "age": age,
        "sex": SEX_LABELS.get(patient.sex),
        "race": RACE_LABELS.get(patient.race),
        "occupation": None if pd.isna(occupation_name) else str(occupation_name),
        "state": UF_ABBR_LABELS.get(state_code),
        "municipality": (
            municipality["name"]
            if municipality is not None
            else (
                str(municipality_code)
                if municipality_code is not None
                else None
            )
        ),
        "symptoms": symptom_labels,
    }


def _simulation_pool_is_valid(pool: pd.DataFrame) -> bool:
    if pool.empty or not set(SIMULATION_POOL_COLUMNS).issubset(pool.columns):
        return False

    dates = pd.to_datetime(pool["notification_date"], errors="coerce")
    years = pd.to_numeric(pool["notification_year"], errors="coerce")
    classifications = pd.to_numeric(
        pool["final_classification_code"],
        errors="coerce",
    )

    return bool(
        dates.notna().all()
        and (years == SIMULATION_YEAR).all()
        and (dates.dt.month >= SIMULATION_NOTIFICATION_MONTH_MIN).all()
        and classifications.isin(SIMULATION_VALID_CLASSIFICATIONS).all()
        and pool["final_classification_label"].notna().all()
    )


def _build_simulation_pool() -> pd.DataFrame:
    """Build the public simulation pool from the untouched 2021 test set."""
    if not SIMULATION_SOURCE_PARQUET.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Base processada de 2021 não encontrada: "
                f"{SIMULATION_SOURCE_PARQUET}"
            ),
        )

    try:
        source = pd.read_parquet(
            SIMULATION_SOURCE_PARQUET,
            columns=list(
                SIMULATION_SOURCE_COLUMNS + SIMULATION_DERIVED_COLUMNS
            ),
        )
        # Contexto epidemiológico calculado sobre TODAS as notificações de 2021
        # (antes de filtrar), para bater exatamente com o dataset de treino/teste.
        source["local_density"] = compute_local_density(source).to_numpy()
        source["local_positivity"] = compute_local_positivity(source).to_numpy()
        dates = pd.to_datetime(source["notification_date"], errors="coerce")
        years = pd.to_numeric(
            source["notification_year"],
            errors="coerce",
        )
        classifications = pd.to_numeric(
            source["final_classification_code"],
            errors="coerce",
        )
        eligible = (
            years.eq(SIMULATION_YEAR)
            & dates.dt.month.ge(SIMULATION_NOTIFICATION_MONTH_MIN)
            & classifications.isin(SIMULATION_VALID_CLASSIFICATIONS)
        )
        filtered = source.loc[
            eligible,
            list(SIMULATION_POOL_COLUMNS),
        ].reset_index(drop=True)
        if not _simulation_pool_is_valid(filtered):
            raise ValueError("pool reduzido da simulação ficou inválido")

        SIMULATION_POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
        filtered.to_parquet(SIMULATION_POOL_PATH, index=False)
        return filtered
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Não foi possível gerar o pool da simulação")
        raise HTTPException(
            status_code=503,
            detail="Não foi possível preparar a base histórica da simulação",
        ) from exc


def _load_simulation_pool() -> pd.DataFrame:
    global _simulation_pool
    if _simulation_pool is not None:
        return _simulation_pool

    with _simulation_pool_lock:
        if _simulation_pool is not None:
            return _simulation_pool

        pool = None
        source_is_newer = (
            SIMULATION_POOL_PATH.exists()
            and SIMULATION_SOURCE_PARQUET.exists()
            and SIMULATION_SOURCE_PARQUET.stat().st_mtime
            > SIMULATION_POOL_PATH.stat().st_mtime
        )

        if SIMULATION_POOL_PATH.exists() and not source_is_newer:
            try:
                candidate = pd.read_parquet(
                    SIMULATION_POOL_PATH,
                    columns=list(SIMULATION_POOL_COLUMNS),
                )
                if _simulation_pool_is_valid(candidate):
                    pool = candidate
                else:
                    logger.warning(
                        "Pool da simulacao existente e invalido; regenerando"
                    )
            except Exception:
                logger.exception(
                    "Nao foi possivel carregar %s; regenerando",
                    SIMULATION_POOL_PATH,
                )

        if pool is None:
            pool = _build_simulation_pool()

        _simulation_pool = pool.reset_index(drop=True)
        return _simulation_pool


def escolher_caso_real_simulacao(seed: int | None = None) -> dict[str, Any]:
    pool = _load_simulation_pool()
    rng = np.random.default_rng(seed)

    for _ in range(MAX_SAMPLE_ATTEMPTS):
        sampled_idx = int(rng.integers(0, len(pool)))
        row = pool.iloc[sampled_idx]

        try:
            classification = _to_int(
                row.get("final_classification_code")
            )
            observed = DENGUE_CLASSIFICATION_LABELS.get(classification)
            if observed is None:
                raise ValueError("classificacao observada invalida")

            patient = _build_patient_from_sample(row)
            anonymized_case = _anonymized_case_from_sample(row, patient)
        except (ValidationError, ValueError, TypeError, OverflowError) as exc:
            logger.warning(
                "Caso historico rejeitado no indice %s: %s",
                sampled_idx,
                exc,
            )
            continue

        return {
            "sampled_index": sampled_idx,
            "patient": patient,
            "case": anonymized_case,
            "observed_classification": observed,
            "local_density": row.get("local_density"),
            "local_positivity": row.get("local_positivity"),
        }

    raise HTTPException(
        status_code=503,
        detail="Nao foi possivel selecionar um caso historico valido",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    faltantes = [
        nome for nome in MODELOS_DISPONIVEIS if nome not in modelos
    ]
    ensemble_ready = (
        set(ENSEMBLE_WEIGHTS) == set(MODELOS_DISPONIVEIS)
        and 0 <= ENSEMBLE_THRESHOLD <= 1
    )
    diseases = {}
    for disease, bundle in MODEL_BUNDLES.items():
        active_models = (
            modelos if disease == "dengue" else bundle["models"]
        )
        missing = [
            name
            for name in MODELOS_DISPONIVEIS
            if name not in active_models
        ]
        diseases[disease] = {
            "status": (
                "ok"
                if not missing and bundle["artifact_compatible"]
                else "degraded"
            ),
            "modelos_carregados": list(active_models),
            "modelos_ausentes": missing,
            "erros_carregamento": bundle["loading_errors"],
            "artefatos_compativeis": bundle["artifact_compatible"],
            "periodos": bundle["manifest"].get("periods", {}),
        }
    return {
        "status": (
            "ok"
            if not faltantes and artifact_set_compatible and ensemble_ready
            else "degraded"
        ),
        "modelos_carregados": list(modelos.keys()),
        "modelos_ausentes": faltantes,
        "erros_carregamento": erros_carregamento,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "artefatos_compativeis": artifact_set_compatible,
        "lookups_contexto_compativeis": context_lookups_compatible,
        "lookups_contexto": {
            "local_density": len(LOCAL_DENSITY_LOOKUP),
            "local_positivity": len(LOCAL_POSITIVITY_LOOKUP),
        },
        "periodos": model_manifest.get("periods", {}),
        "ensemble_threshold": ENSEMBLE_THRESHOLD,
        "ensemble_weights": ENSEMBLE_WEIGHTS,
        "doencas": diseases,
    }


@app.post("/predict")
def predict(dados: DadosPaciente):
    _exigir_conjunto_completo_de_modelos(dados.disease)
    df = construir_features(dados)

    return _inferir_modelos(df, dados.disease)


@app.post("/api/v1/simulations/random")
def simulation_random(payload: SimulacaoRandomRequest | None = None):
    _exigir_conjunto_completo_de_modelos("dengue")

    sample = escolher_caso_real_simulacao(seed=(payload.seed if payload else None))
    # Caso histórico: usa a densidade/positividade EXATAS de 2021 (as que o modelo
    # viu no teste), não a média sazonal do lookup.
    features = construir_features(
        sample["patient"],
        local_density=[float(sample["local_density"])],
        local_positivity=[float(sample["local_positivity"])],
    )
    prediction = _inferir_modelos(features, "dengue")

    if prediction["ignored"]:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Nem todos os modelos conseguiram gerar predição",
                "ignored": prediction["ignored"],
            },
        )

    return {
        "case": sample["case"],
        "observedClassification": sample["observed_classification"],
        "prediction": {
            "disease": prediction["disease"],
            "models": prediction["models"],
            "average": prediction["average"],
            "threshold": prediction["threshold"],
            "weighting": prediction["weighting"],
            "isPositive": prediction["isPositive"],
            "isDengue": prediction["isDengue"],
            "isChikungunya": prediction["isChikungunya"],
        },
    }

# ---------------------------------------------------------------------------
# Dados de referência — municípios
# ---------------------------------------------------------------------------

def _norm(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto.lower())
        .encode("ascii", "ignore")
        .decode()
    )

def _carregar_municipios_ref() -> list[dict]:
    import json
    caminho = Path(__file__).parent / "data" / "municipios.json"
    if not caminho.exists():
        return []
    raw = json.loads(caminho.read_text(encoding="utf-8"))
    resultado = []
    for m in raw:
        uf = ((m.get("microrregiao") or {}).get("mesorregiao") or {}).get("UF") or {}
        nome = m.get("nome", "")
        resultado.append({
            "code": m["id"],
            "name": nome,
            "stateCode": uf.get("id", 0),
            "state": uf.get("sigla", ""),
            "name_norm": _norm(nome),
        })
    return resultado

_MUNICIPIOS_REF = _carregar_municipios_ref()
_MUNICIPIOS_BY_SINAN_CODE = {
    int(municipio["code"]) // 10: municipio
    for municipio in _MUNICIPIOS_REF
}

# Regiões de saúde por município (carrega data/regioes_saude.json se existir)
def _carregar_regioes_ref() -> dict[int, list[dict]]:
    import json
    caminho = Path(__file__).parent / "data" / "regioes_saude.json"
    if not caminho.exists():
        return {}
    raw = json.loads(caminho.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}

_REGIOES_REF = _carregar_regioes_ref()

# Ocupações para busca
_OCUPACOES_REF = [
    {
        "code": str(v),
        "name": k.title(),
        "name_norm": _norm(k),
    }
    for k, v in CBO_MAP.items()
]

DENGUE_THRESHOLD = round(ENSEMBLE_THRESHOLD * 100, 1)

# ---------------------------------------------------------------------------
# GET /api/v1/triage/options
# ---------------------------------------------------------------------------

@app.get("/api/v1/triage/options")
def triage_options():
    """Retorna todas as listas de opções necessárias para o formulário de triagem."""
    ufs = [
        {"code": code, "sigla": sigla, "name": UF_LABELS[code]}
        for code, sigla in UF_ABBR_LABELS.items()
    ]
    return {
        "doencas": [
            {"code": "dengue", "name": "Dengue"},
            {"code": "chikungunya", "name": "Chikungunya"},
        ],
        "sexos": [
            {"code": k, "name": v} for k, v in SEX_LABELS.items()
        ],
        "racas": [
            {"code": k, "name": v} for k, v in RACE_LABELS.items()
        ],
        "escolaridades": [
            {"code": k, "name": v} for k, v in EDUCATION_LABELS.items()
        ],
        "situacoesGestacao": [
            {"code": k, "name": v} for k, v in PREGNANCY_LABELS.items()
        ],
        "sintomas": [
            {"id": "fever",              "label": "Febre"},
            {"id": "myalgia",            "label": "Mialgia / dor muscular"},
            {"id": "headache",           "label": "Cefaleia / dor de cabeça"},
            {"id": "rash",               "label": "Exantema / manchas na pele"},
            {"id": "vomiting",           "label": "Vômitos"},
            {"id": "nausea",             "label": "Náusea / enjoo"},
            {"id": "back_pain",          "label": "Dor nas costas"},
            {"id": "conjunctivitis",     "label": "Conjuntivite"},
            {"id": "arthritis",          "label": "Artrite"},
            {"id": "joint_pain",         "label": "Dor nas articulações"},
            {"id": "petechiae",          "label": "Petéquias / pontos vermelhos na pele"},
            {"id": "retro_orbital_pain", "label": "Dor atrás dos olhos"},
        ],
        "ufs": ufs,
        "modelosAtivos": list(modelos.keys()),
        "modelosPorDoenca": {
            disease: list(
                (
                    modelos
                    if disease == "dengue"
                    else bundle["models"]
                ).keys()
            )
            for disease, bundle in MODEL_BUNDLES.items()
        },
        "limiarClassificacao": DENGUE_THRESHOLD,
        # Compatibilidade temporária com clientes que consumiam a chave grafada
        # incorretamente antes da versão 1.0.
        "liamiarClassificacao": DENGUE_THRESHOLD,
        "pesosModelos": ENSEMBLE_WEIGHTS,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/references/occupations
# ---------------------------------------------------------------------------

@app.get("/api/v1/references/occupations")
def buscar_ocupacoes(
    query: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
):
    """Busca ocupações CBO por nome. Prioriza matches que começam com o texto."""
    q = _norm(query)
    starts   = [o for o in _OCUPACOES_REF if o["name_norm"].startswith(q)]
    contains = [o for o in _OCUPACOES_REF if not o["name_norm"].startswith(q) and q in o["name_norm"]]
    resultado = (starts + contains)[:limit]
    return {"items": [{"code": o["code"], "name": o["name"]} for o in resultado]}


# ---------------------------------------------------------------------------
# GET /api/v1/references/municipalities
# ---------------------------------------------------------------------------

@app.get("/api/v1/references/municipalities")
def buscar_municipios(
    query: str = Query(..., min_length=2),
    state: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Busca municípios por nome, com filtro opcional por código IBGE da UF."""
    if not _MUNICIPIOS_REF:
        raise HTTPException(
            status_code=503,
            detail="Base de municípios não encontrada. Adicione data/municipios.json.",
        )
    q = _norm(query)
    pool = [m for m in _MUNICIPIOS_REF if state is None or m["stateCode"] == state]
    starts   = [m for m in pool if m["name_norm"].startswith(q)]
    contains = [m for m in pool if not m["name_norm"].startswith(q) and q in m["name_norm"]]
    resultado = (starts + contains)[:limit]
    return {
        "items": [
            {
                "code": m["code"],
                "name": m["name"],
                "stateCode": m["stateCode"],
                "state": m["state"],
            }
            for m in resultado
        ]
    }


# ---------------------------------------------------------------------------
# GET /api/v1/references/health-regions
# ---------------------------------------------------------------------------

@app.get("/api/v1/references/health-regions")
def buscar_regioes_saude(municipality: int = Query(...)):
    """Retorna as regiões de saúde associadas a um município (código IBGE)."""
    regioes = _REGIOES_REF.get(municipality, [])
    return {"items": regioes}
