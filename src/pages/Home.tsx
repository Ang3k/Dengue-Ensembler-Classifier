import PredictionSimulator from "../components/PredictionSimulator";

const metricas = [
  {
    valor: "72,1%",
    nome: "Accuracy",
    explicacao:
      "Acertou a classificação de 677.991 dos 940.304 registros avaliados.",
  },
  {
    valor: "72,6%",
    nome: "Balanced Accuracy",
    explicacao:
      "Média do desempenho entre confirmados e descartados, sem favorecer uma classe.",
  },
  {
    valor: "66,1%",
    nome: "Precision",
    explicacao:
      "De cada 100 casos marcados como dengue, cerca de 66 eram confirmados.",
  },
  {
    valor: "87,3%",
    nome: "Recall",
    explicacao:
      "Encontrou cerca de 87 de cada 100 casos de dengue realmente confirmados.",
  },
  {
    valor: "57,9%",
    nome: "Specificity",
    explicacao:
      "Reconheceu corretamente cerca de 58 de cada 100 casos descartados.",
  },
  {
    valor: "82,9%",
    nome: "ROC-AUC",
    explicacao:
      "Mede a capacidade de separar confirmados e descartados em diferentes limiares.",
  },
];

function Home() {
  return (
    <main className="container">
      <section className="card">
        <h1>Dengue Sense Classifier</h1>

        <p>
          O Dengue Sense Classifier é um projeto de aprendizado de máquina
          aplicado à epidemiologia da dengue. A partir de registros oficiais do
          SINAN, três modelos aprendem a distinguir casos{" "}
          <strong>confirmados</strong> de <strong>descartados</strong> e são
          combinados em um ensemble. O resultado é um score de classificação
          para apoio à triagem — não uma probabilidade clínica nem um
          diagnóstico.
        </p>

        <div className="home-section">
          <h2>Como funciona</h2>
          <p>
            Na página de <strong>Triagem</strong>, você informa dados disponíveis
            no momento da notificação, como idade, localização, datas e sintomas.
            O sistema transforma esses campos nas mesmas variáveis usadas durante
            o treino e devolve os scores da MLP, do XGBoost e do LightGBM, além da
            classificação combinada.
          </p>
          <p>
            A página de <strong>Pipeline</strong> mostra o caminho completo dos
            dados, incluindo a otimização com Optuna. O{" "}
            <strong>Panorama Epidemiológico</strong> reúne os gráficos históricos
            da análise de 2017 a 2019.
          </p>
          <p>
            <em>
              Na simulação abaixo, o sistema seleciona um registro anonimizado do
              teste de 2021 e compara a classificação registrada no SINAN com os
              scores calculados pelos modelos.
            </em>
          </p>
        </div>

        <div className="home-section">
          <h2>Sobre os dados</h2>
          <p>
            O projeto processou <strong>11.441.770 notificações</strong> do SINAN
            entre 2014 e 2021. Depois da harmonização das classificações e da
            remoção de casos sem rótulo utilizável, restaram{" "}
            <strong>9.995.416 registros</strong> confirmados ou descartados para
            auditoria.
          </p>
          <p>
            Os anos de 2014 a 2016 não entram no modelo porque os campos de
            sintomas estão ausentes ou incompletos. O treino usa{" "}
            <strong>2.874.235 casos de 2017 a 2019</strong>; 2020 é reservado para
            validação, Optuna e escolha do limiar; e os{" "}
            <strong>940.304 casos de 2021</strong> formam o teste final, sem
            participar de nenhuma decisão de treinamento.
          </p>
        </div>

        <div className="home-section">
          <h2>Sobre o modelo</h2>
          <p>
            O esquema atual possui <strong>107 variáveis</strong>: dados
            demográficos, localização, 12 sintomas e suas combinações, intervalo
            até a notificação, sazonalidade e o contexto epidemiológico recente
            do município. Comparamos uma rede neural MLP, XGBoost e LightGBM e
            combinamos seus scores com pesos definidos pelo desempenho na
            validação de 2020.
          </p>
          <p>
            Nenhuma informação de exame, evolução, hospitalização ou encerramento
            do caso atual entra no modelo. O ano também fica de fora. O ensemble
            usa um ponto de operação manual de <strong>30%</strong>, definido com
            a validação de 2020 para priorizar sensibilidade antes da avaliação
            final em 2021.
          </p>
        </div>

        <div className="home-section home-resultados">
          <h2>Resultados no teste de 2021</h2>
          <p className="metricas-contexto">
            Os números abaixo são do ensemble no conjunto temporal de 2021, que
            contém 455.718 casos confirmados e 484.586 descartados.
          </p>

          <div className="metricas-grid" aria-label="Métricas do ensemble">
            {metricas.map((metrica) => (
              <article className="metrica-card" key={metrica.nome}>
                <strong className="metrica-valor">{metrica.valor}</strong>
                <span className="metrica-nome">{metrica.nome}</span>
                <p>{metrica.explicacao}</p>
              </article>
            ))}
          </div>

          <p className="metricas-nota">
            O ensemble também obteve F1 de 75,2% e PR-AUC de 82,1%. As métricas
            descrevem o desempenho neste conjunto histórico e não garantem o
            mesmo resultado em outros períodos ou contextos epidemiológicos.
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
