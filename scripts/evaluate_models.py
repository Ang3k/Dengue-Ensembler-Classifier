from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    classification_report,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_curve,
    roc_auc_score,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dengue_pipeline.datasets import (  # noqa: E402
    load_ml_years,
    split_features_target,
)
from dengue_pipeline.diseases import get_disease_config  # noqa: E402
from dengue_pipeline.features import (  # noqa: E402
    FEATURE_SCHEMA_VERSION,
    MODEL_FEATURE_COLUMNS,
)
from dengue_pipeline.paths import (  # noqa: E402
    disease_ensemble_config_path,
    disease_model_figures_dir,
    disease_model_manifest_path,
    disease_models_dir,
)


MODEL_FILES = {
    "mlp": "mlp.joblib",
    "xgboost": "xgboost.joblib",
    "lightgbm": "lightgbm.joblib",
}

MODEL_ORDER = ("mlp", "xgboost", "lightgbm", "ensemble")
MODEL_LABELS = {
    "mlp": "MLP",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "ensemble": "Ensemble",
}
MODEL_COLORS = {
    "mlp": "#2563EB",
    "xgboost": "#0F766E",
    "lightgbm": "#7C3AED",
    "ensemble": "#DC2626",
}


def style_axis(axis, *, grid: bool = True) -> None:
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.tick_params(axis="both", which="both", length=0, labelsize=11)
    if grid:
        axis.grid(
            True,
            color="#D8DEE8",
            linestyle="--",
            linewidth=0.8,
            alpha=0.7,
        )
        axis.set_axisbelow(True)


def save_figure(fig, destination: Path) -> None:
    fig.savefig(
        destination,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def positive_probability(model, features: pd.DataFrame) -> np.ndarray:
    values = np.asarray(model.predict_proba(features))
    return values[:, 1] if values.ndim == 2 else values.reshape(-1)


def threshold_metrics(
    model_name: str,
    split: str,
    target: np.ndarray,
    scores: np.ndarray,
    thresholds: np.ndarray,
) -> pd.DataFrame:
    rows = []
    for threshold in thresholds:
        predictions = (scores >= threshold).astype("int8")
        tn, fp, fn, tp = confusion_matrix(
            target,
            predictions,
            labels=[0, 1],
        ).ravel()
        rows.append(
            {
                "model": model_name,
                "split": split,
                "threshold": float(threshold),
                "accuracy": accuracy_score(target, predictions),
                "balanced_accuracy": balanced_accuracy_score(
                    target,
                    predictions,
                ),
                "precision": precision_score(
                    target,
                    predictions,
                    zero_division=0,
                ),
                "recall": recall_score(
                    target,
                    predictions,
                    zero_division=0,
                ),
                "specificity": tn / max(tn + fp, 1),
                "f1": f1_score(target, predictions, zero_division=0),
                "predicted_positive_rate": predictions.mean(),
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
                "tp": int(tp),
            }
        )
    return pd.DataFrame(rows)


def select_threshold(metrics: pd.DataFrame) -> pd.Series:
    # Youden J = sensibilidade + especificidade - 1, que é monotônico com a
    # balanced accuracy. Escolhe um ponto de operação equilibrado em vez de
    # maximizar F1 (que, sob a prevalência de 2020, empurrava o limiar pra
    # baixo e fazia o modelo prever "confirmado" pra quase todo mundo).
    return metrics.sort_values(
        ["balanced_accuracy", "f1"],
        ascending=False,
    ).iloc[0]


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_models(manifest: dict, models_dir: Path) -> dict:
    loaded = {}
    for name, filename in MODEL_FILES.items():
        path = models_dir / filename
        entry = manifest.get("models", {}).get(name, {})
        if entry.get("file") != filename:
            raise RuntimeError(f"{name} filename differs from model manifest")
        if not path.exists() or entry.get("sha256") != file_sha256(path):
            raise RuntimeError(f"{name} SHA-256 differs from model manifest")
        model = joblib.load(path)
        if name == "xgboost":
            internal_model = getattr(model, "model", None)
            if hasattr(internal_model, "set_params"):
                internal_model.set_params(
                    device=os.getenv("XGBOOST_DEVICE", "cpu")
                )
        loaded[name] = model
    return loaded


def save_evaluation_figures(
    validation_metrics: pd.DataFrame,
    test_metrics: pd.DataFrame,
    confusion_rows: pd.DataFrame,
    curve_scores: dict[str, np.ndarray],
    y_test: np.ndarray,
    evaluation_figures_dir: Path,
    disease_label: str,
    validation_year: int,
    test_year: int,
) -> None:
    evaluation_figures_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titleweight": "semibold",
            "axes.labelsize": 12,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )

    metric_specs = (
        ("accuracy", "Acurácia"),
        ("balanced_accuracy", "Acurácia\nbalanceada"),
        ("precision", "Precisão"),
        ("recall", "Recall"),
        ("f1", "F1-score"),
        ("roc_auc", "ROC-AUC"),
        ("pr_auc", "PR-AUC"),
    )
    indexed_metrics = test_metrics.set_index("model")
    x_positions = np.arange(len(metric_specs))
    bar_width = 0.19
    fig, axis = plt.subplots(figsize=(14, 7))
    for model_index, name in enumerate(MODEL_ORDER):
        values = [indexed_metrics.loc[name, metric] for metric, _ in metric_specs]
        positions = x_positions + (model_index - 1.5) * bar_width
        bars = axis.bar(
            positions,
            values,
            width=bar_width,
            color=MODEL_COLORS[name],
            label=MODEL_LABELS[name],
            alpha=0.94,
        )
        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.014,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                rotation=90,
                fontsize=8.5,
                color="#334155",
            )
    axis.set_xticks(x_positions, [label for _, label in metric_specs])
    axis.set_ylim(0, 1.09)
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.set_ylabel("Resultado")
    axis.set_title(
        f"Comparação das métricas — {disease_label}",
        fontsize=20,
        pad=52,
    )
    axis.text(
        0.5,
        1.035,
        f"Teste temporal final de {test_year}",
        transform=axis.transAxes,
        ha="center",
        fontsize=11,
        color="#64748B",
    )
    axis.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.14),
        ncol=4,
        frameon=False,
        fontsize=11,
    )
    style_axis(axis)
    fig.tight_layout()
    save_figure(
        fig,
        evaluation_figures_dir / "model_metrics_comparison.png",
    )

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, sharey=True)
    for axis, name in zip(axes.ravel(), MODEL_ORDER):
        group = validation_metrics[validation_metrics["model"] == name]
        selected = group[group["selected"]]
        axis.plot(
            group["threshold"],
            group["precision"],
            color="#2563EB",
            linewidth=2.7,
            label="Precisão",
        )
        axis.plot(
            group["threshold"],
            group["recall"],
            color="#DC2626",
            linewidth=2.7,
            label="Recall",
        )
        axis.plot(
            group["threshold"],
            group["f1"],
            color="#0F766E",
            linewidth=2.7,
            label="F1-score",
        )
        if not selected.empty:
            selected_threshold = float(selected.iloc[0]["threshold"])
            axis.axvline(
                selected_threshold,
                color="#94A3B8",
                linestyle="--",
                linewidth=1.4,
            )
            axis.text(
                selected_threshold,
                0.025,
                f" {selected_threshold:.2f}",
                rotation=90,
                va="bottom",
                ha="left",
                fontsize=8.5,
                color="#64748B",
            )
        axis.set_title(MODEL_LABELS[name], fontsize=15, pad=10)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1.02)
        axis.set_xlabel("Limiar")
        axis.set_ylabel("Resultado")
        style_axis(axis)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=3,
        frameon=False,
        fontsize=11,
    )
    fig.suptitle(
        f"Precisão, Recall e F1 por limiar — {disease_label}",
        fontsize=20,
        fontweight="semibold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.955,
        f"Limiar definido exclusivamente na validação de {validation_year}",
        ha="center",
        fontsize=11,
        color="#64748B",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    save_figure(fig, evaluation_figures_dir / "threshold_analysis.png")

    fig, axes = plt.subplots(2, 2, figsize=(12, 11))
    image = None
    for axis, name in zip(axes.ravel(), MODEL_ORDER):
        matrix = (
            confusion_rows[confusion_rows["model"] == name]
            .pivot(index="actual", columns="predicted", values="count")
            .reindex(index=[0, 1], columns=[0, 1], fill_value=0)
            .to_numpy()
        )
        row_totals = matrix.sum(axis=1, keepdims=True)
        proportions = np.divide(
            matrix,
            row_totals,
            out=np.zeros_like(matrix, dtype=float),
            where=row_totals != 0,
        )
        image = axis.imshow(proportions, cmap="Blues", vmin=0, vmax=1)
        axis.set_title(MODEL_LABELS[name], fontsize=15, pad=10)
        axis.set_xticks([0, 1], ["Descartado", "Confirmado"])
        axis.set_yticks([0, 1], ["Descartado", "Confirmado"])
        axis.set_xlabel("Classe prevista")
        axis.set_ylabel("Classe real")
        for row in range(2):
            for column in range(2):
                proportion = proportions[row, column]
                axis.text(
                    column,
                    row,
                    (
                        f"{int(matrix[row, column]):,}".replace(",", ".")
                        + f"\n({proportion:.1%})"
                    ),
                    ha="center",
                    va="center",
                    color="white" if proportion >= 0.52 else "#0F172A",
                    fontsize=12,
                    fontweight="semibold",
                )
        style_axis(axis, grid=False)
    colorbar = fig.colorbar(
        image,
        ax=axes.ravel().tolist(),
        fraction=0.028,
        pad=0.035,
    )
    colorbar.set_label("Proporção dentro da classe real", fontsize=11)
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    colorbar.outline.set_visible(False)
    fig.suptitle(
        f"Matrizes de confusão — {disease_label}",
        fontsize=20,
        fontweight="semibold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.945,
        f"Teste temporal final de {test_year}",
        ha="center",
        fontsize=11,
        color="#64748B",
    )
    fig.subplots_adjust(top=0.88, bottom=0.06, left=0.08, right=0.88, hspace=0.3)
    save_figure(fig, evaluation_figures_dir / "confusion_matrices.png")

    metric_lookup = test_metrics.set_index("model")
    fig, axis = plt.subplots(figsize=(10, 8))
    for name in MODEL_ORDER:
        scores = curve_scores[name]
        false_positive, true_positive, _ = roc_curve(y_test, scores)
        axis.plot(
            false_positive,
            true_positive,
            color=MODEL_COLORS[name],
            linewidth=3.0 if name == "ensemble" else 2.5,
            label=(
                f"{MODEL_LABELS[name]} "
                f"(AUC = {metric_lookup.loc[name, 'roc_auc']:.3f})"
            ),
        )
    axis.plot(
        [0, 1],
        [0, 1],
        linestyle="--",
        linewidth=1.5,
        color="#94A3B8",
        label="Aleatório",
    )
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1.02)
    axis.set_xlabel("Taxa de falsos positivos (1 − especificidade)")
    axis.set_ylabel("Taxa de verdadeiros positivos (recall)")
    fig.suptitle(
        f"Curvas ROC — {disease_label}",
        fontsize=20,
        fontweight="semibold",
        y=0.985,
    )
    axis.set_title(
        f"Teste temporal final de {test_year}",
        fontsize=11,
        color="#64748B",
        pad=14,
    )
    axis.legend(loc="lower right", frameon=False, fontsize=11)
    style_axis(axis)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    save_figure(fig, evaluation_figures_dir / "roc_curves.png")

    fig, axis = plt.subplots(figsize=(10, 8))
    for name in MODEL_ORDER:
        scores = curve_scores[name]
        precision, recall, _ = precision_recall_curve(y_test, scores)
        axis.plot(
            recall,
            precision,
            color=MODEL_COLORS[name],
            linewidth=3.0 if name == "ensemble" else 2.5,
            label=(
                f"{MODEL_LABELS[name]} "
                f"(AP = {metric_lookup.loc[name, 'pr_auc']:.3f})"
            ),
        )
    prevalence = float(np.mean(y_test))
    axis.axhline(
        prevalence,
        color="#94A3B8",
        linestyle="--",
        linewidth=1.5,
        label=f"Baseline ({prevalence:.1%})",
    )
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1.02)
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precisão")
    fig.suptitle(
        f"Curvas Precision-Recall — {disease_label}",
        fontsize=20,
        fontweight="semibold",
        y=0.985,
    )
    axis.set_title(
        f"Teste temporal final de {test_year}",
        fontsize=11,
        color="#64748B",
        pad=14,
    )
    axis.legend(loc="lower left", frameon=False, fontsize=11)
    style_axis(axis)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    save_figure(
        fig,
        evaluation_figures_dir / "precision_recall_curves.png",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate and evaluate one arbovirus model set."
    )
    parser.add_argument(
        "--disease",
        choices=("dengue", "chikungunya"),
        default="dengue",
    )
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument(
        "--ensemble-threshold",
        type=float,
        default=None,
        help=(
            "Fixa o limiar do ensemble (ponto de operação de deploy) em vez de "
            "selecioná-lo por balanced accuracy. Ex.: 0.2 para alta sensibilidade."
        ),
    )
    args = parser.parse_args()
    config = get_disease_config(args.disease)
    models_dir = disease_models_dir(config.name)
    model_manifest_path = disease_model_manifest_path(config.name)
    ensemble_config_path = disease_ensemble_config_path(config.name)
    metrics_dir = PROJECT_ROOT / "reports" / "metrics" / "modeling"
    if config.name != "dengue":
        metrics_dir /= config.name
    evaluation_figures_dir = (
        disease_model_figures_dir(config.name) / "evaluation"
    )
    if args.ensemble_threshold is not None and not 0 < args.ensemble_threshold < 1:
        parser.error("--ensemble-threshold deve estar entre 0 e 1")

    manifest = json.loads(
        model_manifest_path.read_text(encoding="utf-8")
    )
    if (
        manifest.get("disease", "dengue") != config.name
        or
        manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
        or manifest.get("feature_columns") != list(MODEL_FEATURE_COLUMNS)
        or manifest.get("periods")
        != {
            "train": list(config.train_years),
            "validation": list(config.validation_years),
            "test": list(config.test_years),
        }
        or manifest.get("row_counts") != config.expected_split_rows
    ):
        raise RuntimeError("Model manifest feature schema is incompatible")

    validation_dataset = load_ml_years(
        config.validation_years,
        config.name,
    )
    if len(validation_dataset) != config.expected_split_rows["validation"]:
        raise RuntimeError("Validation dataset row count is not official")
    X_validation, y_validation = split_features_target(validation_dataset)
    thresholds = np.arange(
        args.threshold_step,
        0.951,
        args.threshold_step,
    ).round(4)

    models = load_models(manifest, models_dir)
    validation_scores = {
        name: positive_probability(model, X_validation)
        for name, model in models.items()
    }
    validation_frames = []
    selected_rows = []
    recalls = {}
    selected_thresholds = {}
    for name in MODEL_FILES:
        metrics = threshold_metrics(
            name,
            "validation",
            y_validation.to_numpy(),
            validation_scores[name],
            thresholds,
        )
        selected = select_threshold(metrics)
        metrics["selected"] = np.isclose(
            metrics["threshold"],
            selected["threshold"],
        )
        validation_frames.append(metrics)
        selected_thresholds[name] = float(selected["threshold"])
        recalls[name] = float(selected["recall"])
        selected_rows.append(
            {
                "model": name,
                "selection_split": "validation",
                "rule": "max_balanced_accuracy",
                **selected.to_dict(),
            }
        )

    recall_total = sum(recalls.values())
    weights = {
        name: recall / recall_total
        for name, recall in recalls.items()
    }
    ensemble_validation = sum(
        validation_scores[name] * weights[name]
        for name in weights
    )
    ensemble_validation_metrics = threshold_metrics(
        "ensemble",
        "validation",
        y_validation.to_numpy(),
        ensemble_validation,
        thresholds,
    )
    ensemble_selected = select_threshold(ensemble_validation_metrics)
    if args.ensemble_threshold is not None:
        ensemble_threshold = round(float(args.ensemble_threshold), 4)
        threshold_rule = "manual_operating_point"
        ensemble_reported = threshold_metrics(
            "ensemble",
            "validation",
            y_validation.to_numpy(),
            ensemble_validation,
            np.asarray([ensemble_threshold]),
        ).iloc[0]
    else:
        ensemble_threshold = float(ensemble_selected["threshold"])
        threshold_rule = "max_balanced_accuracy"
        ensemble_reported = ensemble_selected
    ensemble_validation_metrics["selected"] = np.isclose(
        ensemble_validation_metrics["threshold"],
        ensemble_threshold,
    )
    validation_frames.append(ensemble_validation_metrics)
    selected_rows.append(
        {
            "model": "ensemble",
            "selection_split": "validation",
            "rule": threshold_rule,
            **ensemble_reported.to_dict(),
            "threshold": ensemble_threshold,
        }
    )

    ensemble_config = {
        "disease": config.name,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "selection_period": list(config.validation_years),
        "test_period": list(config.test_years),
        "threshold_rule": threshold_rule,
        "weight_rule": "normalized_validation_recall",
        "threshold": ensemble_threshold,
        "weights": weights,
        "model_manifest_sha256": file_sha256(model_manifest_path),
    }

    # Only after every decision is frozen do we open the final test set.
    del validation_dataset, X_validation, y_validation
    del validation_scores, ensemble_validation
    gc.collect()
    test_dataset = load_ml_years(config.test_years, config.name)
    if len(test_dataset) != config.expected_split_rows["test"]:
        raise RuntimeError("Test dataset row count is not official")
    X_test, y_test = split_features_target(test_dataset)
    test_scores = {
        name: positive_probability(model, X_test)
        for name, model in models.items()
    }
    ensemble_test = sum(
        test_scores[name] * weights[name]
        for name in weights
    )
    test_metric_rows = []
    confusion_rows = []
    classification_rows = []
    for name, scores in {
        **test_scores,
        "ensemble": ensemble_test,
    }.items():
        threshold = (
            ensemble_threshold
            if name == "ensemble"
            else selected_thresholds[name]
        )
        metric = threshold_metrics(
            name,
            "test",
            y_test.to_numpy(),
            scores,
            np.asarray([threshold]),
        ).iloc[0].to_dict()
        metric.update(
            {
                "roc_auc": roc_auc_score(y_test, scores),
                "pr_auc": average_precision_score(y_test, scores),
                "weight": weights.get(name, 1.0),
            }
        )
        test_metric_rows.append(metric)
        predictions = (scores >= threshold).astype("int8")
        report = classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["discarded", "confirmed"],
            output_dict=True,
            zero_division=0,
        )
        for label, values in report.items():
            if isinstance(values, dict):
                classification_rows.append(
                    {"model": name, "label": label, **values}
                )
        for actual, predicted, count in (
            (0, 0, metric["tn"]),
            (0, 1, metric["fp"]),
            (1, 0, metric["fn"]),
            (1, 1, metric["tp"]),
        ):
            confusion_rows.append(
                {
                    "model": name,
                    "actual": actual,
                    "predicted": predicted,
                    "count": int(count),
                }
            )

    metrics_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(validation_frames, ignore_index=True).to_csv(
        metrics_dir / "threshold_metrics.csv",
        index=False,
    )
    pd.DataFrame(selected_rows).to_csv(
        metrics_dir / "selected_thresholds.csv",
        index=False,
    )
    test_metrics_frame = pd.DataFrame(test_metric_rows)
    test_metrics_frame.to_csv(
        metrics_dir / "model_metrics.csv",
        index=False,
    )
    confusion_frame = pd.DataFrame(confusion_rows)
    confusion_frame.to_csv(
        metrics_dir / "confusion_matrices.csv",
        index=False,
    )
    pd.DataFrame(classification_rows).to_csv(
        metrics_dir / "classification_report.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "split": "test",
                "period_start": f"{config.test_years[0]}-01",
                "period_end": f"{config.test_years[-1]}-12",
                "n_samples": len(y_test),
                "n_features": X_test.shape[1],
                "n_confirmed": int(y_test.sum()),
                "n_discarded": int((y_test == 0).sum()),
                "positive_rate": float(y_test.mean()),
            }
        ]
    ).to_csv(metrics_dir / "test_set_summary.csv", index=False)

    temporary = ensemble_config_path.with_suffix(".json.part")
    temporary.write_text(
        json.dumps(ensemble_config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(ensemble_config_path)
    save_evaluation_figures(
        pd.concat(validation_frames, ignore_index=True),
        test_metrics_frame,
        confusion_frame,
        {**test_scores, "ensemble": ensemble_test},
        y_test.to_numpy(),
        evaluation_figures_dir,
        config.label,
        config.validation_years[0],
        config.test_years[0],
    )
    print(test_metrics_frame.to_string(index=False))
    print(f"Ensemble configuration written to {ensemble_config_path}")


if __name__ == "__main__":
    main()
