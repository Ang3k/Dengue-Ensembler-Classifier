import type { Symptom } from "../types/symptom";

export const symptoms: Symptom[] = [
  {
    id: "febre",
    label: "Febre alta de início repentino",
    points: 3,
  },
  {
    id: "dor_cabeca",
    label: "Dor de cabeça",
    points: 2,
  },
  {
    id: "dor_olhos",
    label: "Dor atrás dos olhos",
    points: 2,
  },
  {
    id: "dor_corpo",
    label: "Dor no corpo ou dores musculares",
    points: 2,
  },
  {
    id: "dor_articulacoes",
    label: "Dor nas articulações",
    points: 2,
  },
  {
    id: "prostracao",
    label: "Moleza, cansaço ou prostração",
    points: 2,
  },
  {
    id: "nausea",
    label: "Enjoo ou náusea",
    points: 1,
  },
  {
    id: "manchas",
    label: "Manchas vermelhas no corpo",
    points: 2,
  },
  {
    id: "dor_abdominal",
    label: "Dor abdominal intensa",
    points: 5,
    alarm: true,
  },
  {
    id: "vomitos",
    label: "Vômitos frequentes",
    points: 5,
    alarm: true,
  },
  {
    id: "tontura",
    label: "Tontura ou sensação de desmaio",
    points: 5,
    alarm: true,
  },
  {
    id: "respirar",
    label: "Dificuldade para respirar",
    points: 5,
    alarm: true,
  },
  {
    id: "sangramento",
    label: "Sangramento no nariz, gengiva ou fezes",
    points: 5,
    alarm: true,
  },
];

export function avaliarDengue(selectedIds: string[]) {
  const selectedSymptoms = symptoms.filter((symptom) =>
    selectedIds.includes(symptom.id)
  );

  const totalPoints = selectedSymptoms.reduce(
    (sum, symptom) => sum + symptom.points,
    0
  );

  const hasFever = selectedIds.includes("febre");

  const commonSymptomsCount = selectedSymptoms.filter(
    (symptom) => !symptom.alarm && symptom.id !== "febre"
  ).length;

  const hasAlarmSign = selectedSymptoms.some((symptom) => symptom.alarm);

  if (hasAlarmSign) {
    return {
      level: "ALERTA",
      title: "Sinais de alarme para dengue grave",
      message:
        "Você marcou pelo menos um sinal de alarme. Procure atendimento médico imediatamente.",
      points: totalPoints,
    };
  }

  if (hasFever && commonSymptomsCount >= 2) {
    return {
      level: "ALTA",
      title: "Alta suspeita de dengue",
      message:
        "Você marcou febre alta e pelo menos dois sintomas compatíveis com dengue. Procure uma unidade de saúde para avaliação.",
      points: totalPoints,
    };
  }

  if (totalPoints >= 5) {
    return {
      level: "MODERADA",
      title: "Suspeita moderada de dengue",
      message:
        "Alguns sintomas são compatíveis com dengue, mas o resultado não confirma a doença. Observe a evolução e procure atendimento se piorar.",
      points: totalPoints,
    };
  }

  return {
    level: "BAIXA",
    title: "Baixa suspeita de dengue",
    message:
      "Pelos sintomas marcados, a suspeita de dengue parece baixa. Mesmo assim, se houver febre persistente ou piora, procure atendimento.",
    points: totalPoints,
  };
}