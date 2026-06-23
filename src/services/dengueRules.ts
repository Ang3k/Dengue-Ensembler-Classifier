import type { PatientData } from "../types/patient";

export type TriageItem = {
  id: string;
  label: string;
  points: number;
  group: "symptoms" | "clinical";
};

export type ModelPrediction = {
  name: string;
  probability: number;
};

export type EvaluationResult = {
  models: ModelPrediction[];
  average: number;
  isDengue: boolean;
};

// Acima deste valor (em %), o resultado final é considerado dengue
export const DENGUE_THRESHOLD = 40;

const MODEL_NAMES = ["Random Forest", "LightGBM", "XGBoost"];

export const triageItems: TriageItem[] = [
  {
    id: "fever",
    label: "Febre",
    points: 3,
    group: "symptoms",
  },
  {
    id: "myalgia",
    label: "Mialgia / dor muscular",
    points: 2,
    group: "symptoms",
  },
  {
    id: "headache",
    label: "Cefaleia / dor de cabeça",
    points: 2,
    group: "symptoms",
  },
  {
    id: "rash",
    label: "Exantema / manchas na pele",
    points: 2,
    group: "symptoms",
  },
  {
    id: "vomiting",
    label: "Vômitos",
    points: 2,
    group: "symptoms",
  },
  {
    id: "nausea",
    label: "Náusea / enjoo",
    points: 1,
    group: "symptoms",
  },
  {
    id: "back_pain",
    label: "Dor nas costas",
    points: 1,
    group: "symptoms",
  },
  {
    id: "conjunctivitis",
    label: "Conjuntivite",
    points: 1,
    group: "symptoms",
  },
  {
    id: "arthritis",
    label: "Artrite",
    points: 1,
    group: "symptoms",
  },
  {
    id: "joint_pain",
    label: "Dor nas articulações",
    points: 2,
    group: "symptoms",
  },
  {
    id: "petechiae",
    label: "Petéquias / pequenos pontos vermelhos na pele",
    points: 2,
    group: "symptoms",
  },
  {
    id: "retro_orbital_pain",
    label: "Dor atrás dos olhos",
    points: 2,
    group: "symptoms",
  },
  {
    id: "tourniquet_test",
    label: "Prova do laço positiva",
    points: 3,
    group: "clinical",
  },
];

export function avaliarDengue(
  selectedIds: string[],
  patientData: PatientData
): EvaluationResult {
  const selectedItems = triageItems.filter((item) =>
    selectedIds.includes(item.id)
  );

  const totalPoints = selectedItems.reduce((sum, item) => {
    return sum + item.points;
  }, 0);

  const hasFever = selectedIds.includes("fever");

  const age = Number(patientData.ageYears || patientData.age);

  const isChild = age > 0 && age < 12;
  const isOlderAdult = age >= 60;

  const isPregnant =
    patientData.pregnancyStatus === "1" ||
    patientData.pregnancyStatus === "2" ||
    patientData.pregnancyStatus === "3" ||
    patientData.pregnancyStatus === "4";

  const wasHospitalized = patientData.hospitalized === "1";

  const daysToNotification = Number(patientData.daysToNotification);
  const delayedNotification = daysToNotification > 5;

  const hasRiskContext =
    isChild || isOlderAdult || isPregnant || wasHospitalized || delayedNotification;

  // Probabilidade base a partir dos sintomas e do contexto informado.
  // Ainda é uma simulação — não vem de um modelo treinado de verdade.
  const base = Math.max(
    5,
    Math.min(
      95,
      10 + totalPoints * 4 + (hasFever ? 12 : 0) + (hasRiskContext ? 8 : 0)
    )
  );

  const models: ModelPrediction[] = MODEL_NAMES.map((name) => {
    const variation = Math.random() * 16 - 8; // entre -8 e +8
    const probability = Math.max(1, Math.min(99, Math.round(base + variation)));
    return { name, probability };
  });

  const average = Math.round(
    models.reduce((sum, model) => sum + model.probability, 0) / models.length
  );

  return { models, average, isDengue: average >= DENGUE_THRESHOLD };
}