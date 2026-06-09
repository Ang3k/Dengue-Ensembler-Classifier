import type { PatientData } from "../types/patient";

export type TriageItem = {
  id: string;
  label: string;
  points: number;
  group: "symptoms" | "clinical";
};

type ModelResult = {
  name: string;
  result: string;
  confidence: string;
  description: string;
};

type EvaluationResult = {
  level: string;
  title: string;
  message: string;
  models: {
    clinical: ModelResult;
    epidemiological: ModelResult;
  };
};

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

  const symptomsCount = selectedItems.filter(
    (item) => item.group === "symptoms"
  ).length;

  const hasTourniquetTest = selectedIds.includes("tourniquet_test");

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

  if (hasFever && symptomsCount >= 4) {
    return {
      level: "ALTA",
      title: "Alta suspeita de dengue",
      message:
        "Os dados informados indicam febre associada a múltiplos sintomas compatíveis com dengue. Recomenda-se procurar uma unidade de saúde para avaliação.",
      models: {
        clinical: {
          name: "Avaliação clínica",
          result: "Compatibilidade alta",
          confidence: "83%",
          description:
            "A avaliação clínica considerou a presença de febre associada a sintomas como dor muscular, cefaleia, dor atrás dos olhos, náuseas, vômitos, exantema ou dor articular.",
        },
        epidemiological: {
          name: "Avaliação epidemiológica",
          result: hasRiskContext
            ? "Risco contextual aumentado"
            : "Risco contextual moderado",
          confidence: hasRiskContext ? "78%" : "68%",
          description:
            "A avaliação contextual considerou idade, sexo, gestação, município de residência, município de notificação, data dos sintomas, hospitalização e tempo até a notificação.",
        },
      },
    };
  }

  if (hasFever && symptomsCount >= 2) {
    return {
      level: "MODERADA",
      title: "Suspeita moderada de dengue",
      message:
        "Há febre associada a alguns sintomas compatíveis com dengue. O resultado não confirma a doença, mas recomenda atenção à evolução do quadro.",
      models: {
        clinical: {
          name: "Avaliação clínica",
          result: "Compatibilidade parcial",
          confidence: "69%",
          description:
            "A combinação de sintomas é compatível com suspeita clínica, mas ainda não representa um conjunto amplo de manifestações.",
        },
        epidemiological: {
          name: "Avaliação epidemiológica",
          result: hasRiskContext
            ? "Atenção ao perfil informado"
            : "Risco contextual intermediário",
          confidence: hasRiskContext ? "72%" : "61%",
          description:
            "Foram considerados dados como idade, gestação, município, unidade notificadora, início dos sintomas e hospitalização.",
        },
      },
    };
  }

  if (hasTourniquetTest || totalPoints >= 7 || hasRiskContext) {
    return {
      level: "MODERADA",
      title: "Atenção aos dados informados",
      message:
        "Alguns sintomas ou dados contextuais merecem atenção. A triagem sugere acompanhamento, principalmente se houver piora ou persistência dos sintomas.",
      models: {
        clinical: {
          name: "Avaliação clínica",
          result: "Achados relevantes",
          confidence: "64%",
          description:
            "A avaliação identificou sinais ou sintomas que podem aparecer em quadros suspeitos de dengue, como prova do laço positiva, petéquias, febre ou dores no corpo.",
        },
        epidemiological: {
          name: "Avaliação epidemiológica",
          result: "Acompanhamento recomendado",
          confidence: "67%",
          description:
            "A análise considerou fatores como idade, gestação, residência, município de notificação, hospitalização e intervalo entre início dos sintomas e notificação.",
        },
      },
    };
  }

  return {
    level: "BAIXA",
    title: "Baixa suspeita de dengue",
    message:
      "Com base nos dados selecionados, a suspeita de dengue parece baixa. Mesmo assim, procure atendimento se houver febre persistente, piora dos sintomas ou surgimento de novos sinais.",
    models: {
      clinical: {
        name: "Avaliação clínica",
        result: "Baixa compatibilidade",
        confidence: "58%",
        description:
          "Poucos sintomas típicos foram informados, reduzindo a compatibilidade clínica com um quadro suspeito de dengue.",
      },
      epidemiological: {
        name: "Avaliação epidemiológica",
        result: "Baixo risco contextual",
        confidence: "55%",
        description:
          "Os dados informados não indicaram, nesta simulação, fatores contextuais suficientes para elevar o nível de atenção.",
      },
    },
  };
}