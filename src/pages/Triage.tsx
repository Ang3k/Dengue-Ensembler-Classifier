import { useState } from "react";
import CheckboxItem from "../components/CheckboxItem";
import PatientForm from "../components/PatientForm";
import Resultado from "../components/Resultado";
import { avaliarDoenca, triageItems } from "../services/dengueRules";
import type {
  Disease,
  EvaluationResult,
} from "../services/dengueRules";
import type { PatientData } from "../types/patient";

const grupos = [
  { id: "symptoms", title: "Sintomas informados" },
];

const estadoInicial: PatientData = {
  ageYears: "",
  sex: "",
  pregnancyStatus: "",
  race: "",
  educationLevel: "",
  occupationCode: "",
  occupationName: "",
  residenceState: "",
  residenceStateLabel: "",
  residenceMunicipality: "",
  residenceMunicipalityName: "",
  residenceHealthRegion: "",
  residenceHealthRegionName: "",
  notificationDate: "",
  symptomOnsetDate: "",
  daysToNotification: "",
  symptomEpiWeekNumber: "",
  symptomEpiYear: "",
};

function Triage() {
  const [disease, setDisease] = useState<Disease>("dengue");
  const [patientData, setPatientData] = useState<PatientData>(estadoInicial);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [resultado, setResultado] = useState<EvaluationResult | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  function toggleItem(id: string) {
    setSelectedItems(current =>
      current.includes(id) ? current.filter(i => i !== id) : [...current, id]
    );
  }

  async function handleEnviarTriagem() {
    setCarregando(true);
    setErro(null);
    setResultado(null);
    try {
      const resultadoFinal = await avaliarDoenca(
        disease,
        selectedItems,
        patientData
      );
      setResultado(resultadoFinal);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Não foi possível concluir a triagem."
      );
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="container">
      <section className="card">
        <h1>Triagem de {disease === "dengue" ? "Dengue" : "Chikungunya"}</h1>
        <p>
          Preencha os dados do paciente e marque os sintomas informados. O
          sistema fará uma triagem baseada nos campos disponíveis na notificação
          de {disease === "dengue" ? "dengue" : "chikungunya"} do Sinan.
        </p>

        <div className="form-group">
          <label htmlFor="disease">Doença avaliada</label>
          <select
            id="disease"
            value={disease}
            onChange={event => {
              setDisease(event.target.value as Disease);
              setResultado(null);
              setErro(null);
            }}
          >
            <option value="dengue">Dengue</option>
            <option value="chikungunya">Chikungunya</option>
          </select>
        </div>

        <PatientForm patientData={patientData} setPatientData={setPatientData} />

        {grupos.map(grupo => {
          const itensDoGrupo = triageItems.filter(item => item.group === grupo.id);
          return (
            <section className="grupo-sintomas" key={grupo.id}>
              <h2>{grupo.title}</h2>
              <div className="checkbox-list">
                {itensDoGrupo.map(item => (
                  <CheckboxItem
                    key={item.id}
                    label={item.label}
                    checked={selectedItems.includes(item.id)}
                    onChange={() => toggleItem(item.id)}
                  />
                ))}
              </div>
            </section>
          );
        })}

        <div className="actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleEnviarTriagem}
            disabled={carregando}
          >
            {carregando ? "Calculando..." : "Enviar triagem"}
          </button>
        </div>

        {erro && <p style={{ color: "red", marginTop: "1rem" }}>{erro}</p>}

        {resultado && (
          <Resultado {...resultado} />
        )}
      </section>
    </main>
  );
}

export default Triage;
