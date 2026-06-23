import PredictionSimulator from "../components/PredictionSimulator";

function Home() {
  return (
    <main className="container">
      <section className="card">
        <h1>Dengue Sense Classifier</h1>

        <p>
          O Dengue Sense Classifier é uma ferramenta de apoio à triagem de
          suspeita de dengue. A partir dos sintomas e dos dados informados sobre
          o paciente, o sistema indica um nível de suspeita — de baixa a alta,
          podendo sinalizar alerta ou sinais de gravidade — para ajudar a
          orientar os próximos passos do atendimento.
        </p>

        <div className="home-section">
          <h2>Como funciona</h2>
          <p>
            Na página de <strong>Triagem</strong>, você preenche os dados
            principais do paciente (como idade, sexo e outras informações) e
            marca os sintomas e achados clínicos observados. Com base nessas
            informações, o sistema analisa o conjunto e apresenta um resultado
            com o nível de suspeita e uma orientação correspondente.
          </p>
          <p>
            Já a página de <strong>Panorama Epidemiológico</strong> reúne
            gráficos e observações sobre os casos de dengue, ajudando a
            visualizar padrões, tendências e características da população
            analisada.
          </p>
        </div>

        <div className="home-section">
          <h2>Sobre os dados</h2>
          <p>
            As análises são construídas a partir de registros oficiais de casos
            de dengue notificados no Brasil, abrangendo um grande volume de
            atendimentos ao longo dos anos. Esses dados permitem entender melhor
            como a doença se manifesta e se distribui entre diferentes perfis de
            pacientes.
          </p>
        </div>

        <PredictionSimulator />

        <p className="home-aviso">
          Esta ferramenta tem caráter informativo e de apoio. Ela não substitui
          a avaliação de um profissional de saúde, que deve sempre ser
          procurado diante de qualquer suspeita de dengue.
        </p>
      </section>
    </main>
  );
}

export default Home;
