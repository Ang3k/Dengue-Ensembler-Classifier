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
      <h2>Dados principais</h2>

      <div className="form-grid">
        <div className="form-group">
          <label>Idade</label>
          <input
            type="number"
            name="age"
            value={patientData.age}
            onChange={handleChange}
            placeholder="Ex: 25"
          />
        </div>

        <div className="form-group">
          <label>Idade em anos</label>
          <input
            type="number"
            name="ageYears"
            value={patientData.ageYears}
            onChange={handleChange}
            placeholder="Ex: 25"
          />
        </div>

        <div className="form-group">
          <label>Sexo</label>
          <select name="sex" value={patientData.sex} onChange={handleChange}>
            <option value="">Selecione</option>
            <option value="M">Masculino</option>
            <option value="F">Feminino</option>
            <option value="I">Ignorado</option>
          </select>
        </div>

        <div className="form-group">
          <label>Status de gestação</label>
          <select
            name="pregnancyStatus"
            value={patientData.pregnancyStatus}
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
          <label>Raça/cor</label>
          <select name="race" value={patientData.race} onChange={handleChange}>
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
            name="educationLevel"
            value={patientData.educationLevel}
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
          <label>Código da ocupação</label>
          <input
            type="text"
            name="occupationCode"
            value={patientData.occupationCode}
            onChange={handleChange}
            placeholder="Ex: 225125"
          />
        </div>

        <div className="form-group">
          <label>Nome da ocupação</label>
          <input
            type="text"
            name="occupationName"
            value={patientData.occupationName}
            onChange={handleChange}
            placeholder="Ex: Médico clínico"
          />
        </div>

        <div className="form-group">
          <label>UF de residência</label>
          <input
            type="text"
            name="residenceState"
            value={patientData.residenceState}
            onChange={handleChange}
            placeholder="Ex: RJ"
            maxLength={2}
          />
        </div>

        <div className="form-group">
          <label>Município de residência</label>
          <input
            type="text"
            name="residenceMunicipality"
            value={patientData.residenceMunicipality}
            onChange={handleChange}
            placeholder="Ex: Rio de Janeiro"
          />
        </div>

        <div className="form-group">
          <label>Região de saúde da residência</label>
          <input
            type="text"
            name="residenceHealthRegion"
            value={patientData.residenceHealthRegion}
            onChange={handleChange}
            placeholder="Ex: Metropolitana I"
          />
        </div>

        <div className="form-group">
          <label>Código da doença</label>
          <input
            type="text"
            name="diseaseCode"
            value={patientData.diseaseCode}
            onChange={handleChange}
            placeholder="Ex: A90"
          />
        </div>

        <div className="form-group">
          <label>Data da notificação</label>
          <input
            type="date"
            name="notificationDate"
            value={patientData.notificationDate}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Semana epidemiológica da notificação</label>
          <input
            type="text"
            name="notificationEpiWeek"
            value={patientData.notificationEpiWeek}
            onChange={handleChange}
            placeholder="Ex: 202412"
          />
        </div>

        <div className="form-group">
          <label>Município de notificação</label>
          <input
            type="text"
            name="notifMunicipality"
            value={patientData.notifMunicipality}
            onChange={handleChange}
            placeholder="Ex: Rio de Janeiro"
          />
        </div>

        <div className="form-group">
          <label>Região de saúde da notificação</label>
          <input
            type="text"
            name="notifHealthRegion"
            value={patientData.notifHealthRegion}
            onChange={handleChange}
            placeholder="Ex: Metropolitana I"
          />
        </div>

        <div className="form-group">
          <label>Unidade de saúde</label>
          <input
            type="text"
            name="healthFacility"
            value={patientData.healthFacility}
            onChange={handleChange}
            placeholder="Ex: UBS Central"
          />
        </div>

        <div className="form-group">
          <label>Data dos primeiros sintomas</label>
          <input
            type="date"
            name="symptomOnsetDate"
            value={patientData.symptomOnsetDate}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Dias até a notificação</label>
          <input
            type="number"
            name="daysToNotification"
            value={patientData.daysToNotification}
            onChange={handleChange}
            placeholder="Ex: 3"
          />
        </div>

        <div className="form-group">
          <label>Ano epidemiológico dos sintomas</label>
          <input
            type="text"
            name="symptomEpiYear"
            value={patientData.symptomEpiYear}
            onChange={handleChange}
            placeholder="Ex: 2024"
          />
        </div>

        <div className="form-group">
          <label>Semana epidemiológica dos sintomas</label>
          <input
            type="text"
            name="symptomEpiWeekNumber"
            value={patientData.symptomEpiWeekNumber}
            onChange={handleChange}
            placeholder="Ex: 12"
          />
        </div>

        <div className="form-group">
          <label>Hospitalizado?</label>
          <select
            name="hospitalized"
            value={patientData.hospitalized}
            onChange={handleChange}
          >
            <option value="">Selecione</option>
            <option value="1">Sim</option>
            <option value="2">Não</option>
            <option value="9">Ignorado</option>
          </select>
        </div>

        <div className="form-group">
          <label>UF do hospital</label>
          <input
            type="text"
            name="hospitalState"
            value={patientData.hospitalState}
            onChange={handleChange}
            placeholder="Ex: RJ"
            maxLength={2}
          />
        </div>
      </div>
    </section>
  );
}

export default PatientForm;