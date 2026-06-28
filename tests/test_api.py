import unittest

import numpy as np
import pandas as pd
from pydantic import ValidationError

import api


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.patient = api.DadosPaciente(
            age_years=25,
            sex="F",
            pregnancy_status=5,
            race=4,
            education_level=6,
            occupation_code="225125",
            residence_state=33,
            residence_municipality=3304557,
            residence_health_region=33005,
            notification_date="2019-03-08",
            symptom_onset_date="2019-03-05",
            fever=1,
            myalgia=1,
            headache=1,
        )

    def test_features_include_current_and_legacy_date_columns(self):
        features = api.construir_features(self.patient)

        self.assertEqual(features.loc[0, "notification_month"], 3)
        self.assertEqual(features.loc[0, "symptom_month"], 3)
        self.assertEqual(features.loc[0, "symptom_day"], 5)
        self.assertEqual(features.loc[0, "days_to_notification"], 3)
        self.assertTrue(np.isfinite(features.to_numpy()).all())

    def test_every_loaded_model_receives_all_expected_columns(self):
        if not api.modelos:
            self.skipTest("nenhum artefato de modelo disponível")

        features = api.construir_features(self.patient)
        for name, model in api.modelos.items():
            with self.subTest(model=name):
                aligned, missing = api.alinhar_colunas(features, model)
                self.assertEqual(missing, [])
                self.assertIsNotNone(aligned)

    def test_prediction_uses_every_loaded_model(self):
        if not api.modelos or not api.preprocess:
            self.skipTest("artefatos de inferência indisponíveis")

        result = api.predict(self.patient)
        predicted = {item["name"] for item in result["models"]}

        self.assertEqual(predicted, set(api.modelos))
        self.assertEqual(result["ignored"], [])
        self.assertGreaterEqual(result["average"], 0)
        self.assertLessEqual(result["average"], 100)

    def test_notification_cannot_precede_symptom_onset(self):
        with self.assertRaises(ValidationError):
            api.DadosPaciente(
                notification_date="2019-03-01",
                symptom_onset_date="2019-03-02",
            )

    def test_simulation_pool_filters_second_semester_2019(self):
        try:
            pool = api._load_simulation_pool()
        except Exception as exc:
            self.skipTest(f"pool de simulação indisponível: {exc}")

        years = pd.to_numeric(pool["notification_year"], errors="coerce")
        months = pd.to_datetime(pool["notification_date"], errors="coerce").dt.month

        self.assertFalse(pool.empty)
        self.assertTrue((years == 2019).all())
        self.assertTrue((months >= 6).all())

    def test_simulation_sampler_is_reproducible_with_seed(self):
        try:
            sample_a = api.escolher_caso_real_simulacao(seed=42)
            sample_b = api.escolher_caso_real_simulacao(seed=42)
        except Exception as exc:
            self.skipTest(f"amostragem da simulação indisponível: {exc}")

        self.assertEqual(sample_a["sampled_index"], sample_b["sampled_index"])
        self.assertEqual(sample_a["case"], sample_b["case"])
        self.assertEqual(
            sample_a["observed_classification"],
            sample_b["observed_classification"],
        )

    def test_simulation_random_response_shape_and_all_models(self):
        required_models = set(api.MODELOS_DISPONIVEIS)

        if not required_models.issubset(set(api.modelos)):
            self.skipTest("nem todos os modelos necessários estão carregados")
        if api.OCCUPATION_ENCODER is None or api.RESIDENCE_STATE_ENCODER is None:
            self.skipTest("encoders de pré-processamento indisponíveis")

        result = api.simulation_random(api.SimulacaoRandomRequest(seed=42))

        self.assertEqual(set(result), {"case", "observedClassification", "prediction"})
        self.assertEqual(
            set(result["prediction"]),
            {"models", "average", "isDengue"},
        )

        case = result["case"]
        self.assertEqual(
            set(case),
            {"age", "sex", "race", "occupation", "state", "municipality", "symptoms"},
        )
        self.assertIsInstance(case["symptoms"], list)

        model_names = {item["name"] for item in result["prediction"]["models"]}
        self.assertEqual(model_names, required_models)
        self.assertEqual(len(result["prediction"]["models"]), len(required_models))

        for item in result["prediction"]["models"]:
            self.assertGreaterEqual(item["probability"], 0)
            self.assertLessEqual(item["probability"], 100)

        self.assertGreaterEqual(result["prediction"]["average"], 0)
        self.assertLessEqual(result["prediction"]["average"], 100)
        self.assertIsInstance(result["prediction"]["isDengue"], bool)


if __name__ == "__main__":
    unittest.main()
