import type { PatientData } from "../types/patient";

type PatientFormProps = {
  patientData: PatientData;
  setPatientData: React.Dispatch<React.SetStateAction<PatientData>>;
};

function PatientForm({ patientData, setPatientData }: PatientFormProps) {
  function handleChange(
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) {
    const { name, value } = event.target;

    setPatientData((current) => ({
      ...current,
      [name]: value,
    }));
  }

  return (
    <section className="patient-form">
      <h2>Dados do paciente</h2>

      <div className="form-grid">
        <div className="form-group">
          <label>Idade</label>
          <input
            type="number"
            name="idade"
            value={patientData.idade}
            onChange={handleChange}
            placeholder="Ex: 25"
          />
        </div>

        <div className="form-group">
          <label>Sexo</label>
          <select
            name="sexo"
            value={patientData.sexo}
            onChange={handleChange}
          >
            <option value="">Selecione</option>
            <option value="M">Masculino</option>
            <option value="F">Feminino</option>
            <option value="I">Ignorado</option>
          </select>
        </div>

        <div className="form-group">
          <label>Gestante</label>
          <select
            name="gestante"
            value={patientData.gestante}
            onChange={handleChange}
          >
            <option value="">Selecione</option>
            <option value="1">1º trimestre</option>
            <option value="2">2º trimestre</option>
            <option value="3">3º trimestre</option>
            <option value="4">Idade gestacional ignorada</option>
            <option value="5">Não</option>
            <option value="6">Não se aplica</option>
            <option value="9">Ignorado</option>
          </select>
        </div>

        <div className="form-group">
          <label>Raça/Cor</label>
          <select
            name="racaCor"
            value={patientData.racaCor}
            onChange={handleChange}
          >
            <option value="">Selecione</option>
            <option value="1">Branca</option>
            <option value="2">Preta</option>
            <option value="3">Amarela</option>
            <option value="4">Parda</option>
            <option value="5">Indígena</option>
            <option value="9">Ignorado</option>
          </select>
        </div>

        <div className="form-group">
          <label>Escolaridade</label>
          <select
            name="escolaridade"
            value={patientData.escolaridade}
            onChange={handleChange}
          >
            <option value="">Selecione</option>
            <option value="0">Analfabeto</option>
            <option value="1">1ª a 4ª série incompleta</option>
            <option value="2">4ª série completa</option>
            <option value="3">5ª a 8ª série incompleta</option>
            <option value="4">Ensino fundamental completo</option>
            <option value="5">Ensino médio incompleto</option>
            <option value="6">Ensino médio completo</option>
            <option value="7">Superior incompleto</option>
            <option value="8">Superior completo</option>
            <option value="10">Não se aplica</option>
            <option value="9">Ignorado</option>
          </select>
        </div>

        <div className="form-group">
          <label>Data dos primeiros sintomas</label>
          <input
            type="date"
            name="dataPrimeirosSintomas"
            value={patientData.dataPrimeirosSintomas}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>UF de residência</label>
          <input
            type="text"
            name="ufResidencia"
            value={patientData.ufResidencia}
            onChange={handleChange}
            placeholder="Ex: RJ"
            maxLength={2}
          />
        </div>

        <div className="form-group">
          <label>Município de residência</label>
          <input
            type="text"
            name="municipioResidencia"
            value={patientData.municipioResidencia}
            onChange={handleChange}
            placeholder="Ex: Rio de Janeiro"
          />
        </div>

        <div className="form-group">
          <label>UF de notificação</label>
          <input
            type="text"
            name="ufNotificacao"
            value={patientData.ufNotificacao}
            onChange={handleChange}
            placeholder="Ex: RJ"
            maxLength={2}
          />
        </div>

        <div className="form-group">
          <label>Município de notificação</label>
          <input
            type="text"
            name="municipioNotificacao"
            value={patientData.municipioNotificacao}
            onChange={handleChange}
            placeholder="Ex: Rio de Janeiro"
          />
        </div>

        <div className="form-group">
          <label>Houve hospitalização?</label>
          <select
            name="hospitalizado"
            value={patientData.hospitalizado}
            onChange={handleChange}
          >
            <option value="">Selecione</option>
            <option value="1">Sim</option>
            <option value="2">Não</option>
            <option value="9">Ignorado</option>
          </select>
        </div>
      </div>
    </section>
  );
}

export default PatientForm;