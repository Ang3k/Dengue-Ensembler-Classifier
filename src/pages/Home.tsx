import { Link } from "react-router-dom";

function Home() {
  return (
    <main className="container">
      <section className="card">
        <h1>IML Dengue</h1>

        <p>
          Este projeto é uma ferramenta de triagem para suspeita de
          dengue. Ele permite marcar sintomas comuns e receber uma indicação
          (baixa, moderada ou alta) sobre a probabilidade de dengue. Não
          substitui avaliação médica.
        </p>

        <div style={{ marginTop: 20 }}>
          <Link to="/triagem" className="primary">
            Ir para triagem
          </Link>
        </div>
      </section>
    </main>
  );
}

export default Home;