import { useState } from "react";

// Valores realistas baseados nos mapeamentos em dengue_pipeline.
const SEXOS = ["Masculino", "Feminino"];

const RACAS = ["Branca", "Preta", "Amarela", "Parda", "Indígena"];

const ESCOLARIDADES = [
  "Analfabeto",
  "Ensino fundamental completo",
  "Ensino médio incompleto",
  "Ensino médio completo",
  "Educação superior incompleta",
  "Educação superior completa",
];

const OCUPACOES = [
  "Estudante",
  "Dona de casa",
  "Trabalhador agropecuário em geral",
  "Pedreiro",
  "Motorista de carro de passeio",
  "Vendedor de comércio varejista",
  "Professor de nível médio no ensino fundamental",
  "Técnico de enfermagem",
  "Auxiliar de escritório, em geral",
  "Recepcionista, em geral",
  "Empregado doméstico nos serviços gerais",
  "Cozinheiro geral",
  "Vigilante",
  "Operador de caixa",
];

const SINTOMAS = [
  "Febre",
  "Mialgia / dor muscular",
  "Cefaleia / dor de cabeça",
  "Exantema / manchas na pele",
  "Vômitos",
  "Náusea / enjoo",
  "Dor nas costas",
  "Conjuntivite",
  "Dor nas articulações",
  "Dor atrás dos olhos",
];

const CLASSIFICACOES = [
  "Descartado",
  "Dengue",
  "Dengue com sinais de alarme",
  "Dengue grave",
];

const MODELOS = ["Random Forest", "LightGBM", "XGBoost"];

// Acima deste valor (em %), a predição final é considerada dengue
const LIMIAR_DENGUE = 40;

type Pessoa = {
  idade: number;
  sexo: string;
  raca: string;
  escolaridade: string;
  ocupacao: string;
  sintomas: string[];
  classificacaoReal: string;
};

type Predicao = {
  modelos: { nome: string; probabilidade: number }[];
  media: number;
  ehDengue: boolean;
};

function escolherAleatorio<T>(lista: T[]): T {
  return lista[Math.floor(Math.random() * lista.length)];
}

function gerarPessoa(): Pessoa {
  // Sorteia entre 2 e 5 sintomas, sem repetir
  const sintomasEmbaralhados = [...SINTOMAS].sort(() => Math.random() - 0.5);
  const quantidade = 2 + Math.floor(Math.random() * 4);

  return {
    idade: 1 + Math.floor(Math.random() * 89),
    sexo: escolherAleatorio(SEXOS),
    raca: escolherAleatorio(RACAS),
    escolaridade: escolherAleatorio(ESCOLARIDADES),
    ocupacao: escolherAleatorio(OCUPACOES),
    sintomas: sintomasEmbaralhados.slice(0, quantidade),
    classificacaoReal: escolherAleatorio(CLASSIFICACOES),
  };
}

function gerarPredicao(pessoa: Pessoa): Predicao {
  // Probabilidade base influenciada pela quantidade de sintomas, só para a
  // demonstração ficar mais convincente (ainda não é um modelo real).
  const base = Math.min(85, 15 + pessoa.sintomas.length * 12);

  const modelos = MODELOS.map((nome) => {
    const variacao = Math.random() * 30 - 15; // entre -15 e +15
    const probabilidade = Math.max(1, Math.min(99, Math.round(base + variacao)));
    return { nome, probabilidade };
  });

  const media = Math.round(
    modelos.reduce((soma, modelo) => soma + modelo.probabilidade, 0) /
      modelos.length
  );

  return { modelos, media, ehDengue: media >= LIMIAR_DENGUE };
}

function PredictionSimulator() {
  const [pessoa, setPessoa] = useState<Pessoa | null>(null);
  const [predicao, setPredicao] = useState<Predicao | null>(null);

  function handleGerar() {
    setPessoa(gerarPessoa());
    setPredicao(null);
  }

  function handleRodarPredicao() {
    if (!pessoa) return;
    setPredicao(gerarPredicao(pessoa));
  }

  return (
    <div className="home-section">
      <h2>Simulação de predição</h2>
      <p>
        Gere uma pessoa com dados aleatórios e rode a predição para ver como o
        sistema vai funcionar: três modelos avaliam o caso, cada um com sua
        probabilidade, e a média define o resultado final. Os valores abaixo são
        apenas uma demonstração — ainda não vêm de um modelo treinado de verdade.
      </p>

      <button type="button" className="btn-primary" onClick={handleGerar}>
        Gerar pessoa aleatória
      </button>

      {pessoa && (
        <div className="sim-card">
          <div className="sim-dados">
            <div className="sim-campo">
              <span className="sim-label">Idade</span>
              <span className="sim-valor">{pessoa.idade} anos</span>
            </div>
            <div className="sim-campo">
              <span className="sim-label">Sexo</span>
              <span className="sim-valor">{pessoa.sexo}</span>
            </div>
            <div className="sim-campo">
              <span className="sim-label">Raça/cor</span>
              <span className="sim-valor">{pessoa.raca}</span>
            </div>
            <div className="sim-campo">
              <span className="sim-label">Escolaridade</span>
              <span className="sim-valor">{pessoa.escolaridade}</span>
            </div>
            <div className="sim-campo sim-campo-largo">
              <span className="sim-label">Ocupação</span>
              <span className="sim-valor">{pessoa.ocupacao}</span>
            </div>
          </div>

          <div className="sim-sintomas">
            <span className="sim-label">Sintomas informados</span>
            <div className="sim-tags">
              {pessoa.sintomas.map((sintoma) => (
                <span key={sintoma} className="sim-tag">
                  {sintoma}
                </span>
              ))}
            </div>
          </div>

          <div className="sim-classificacao">
            <span className="sim-label">Classificação real</span>
            <span className="sim-valor-destaque">{pessoa.classificacaoReal}</span>
          </div>

          <button
            type="button"
            className="btn-predicao"
            onClick={handleRodarPredicao}
          >
            Rodar predição
          </button>

          {predicao && (
            <div className="sim-predicao">
              <span className="sim-label">Resultado dos modelos</span>

              <div className="sim-modelos">
                {predicao.modelos.map((modelo) => (
                  <div key={modelo.nome} className="sim-modelo">
                    <div className="sim-modelo-topo">
                      <span className="sim-modelo-nome">{modelo.nome}</span>
                      <span className="sim-modelo-prob">
                        {modelo.probabilidade}%
                      </span>
                    </div>
                    <div className="sim-barra">
                      <div
                        className="sim-barra-preench"
                        style={{ width: `${modelo.probabilidade}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="sim-media">
                <span className="sim-label">Probabilidade média</span>
                <span className="sim-valor-destaque">{predicao.media}%</span>
              </div>

              <div
                className={`sim-veredito ${
                  predicao.ehDengue ? "sim-veredito-dengue" : "sim-veredito-nao"
                }`}
              >
                {predicao.ehDengue ? "É dengue" : "Não é dengue"}
                <small>
                  Média {predicao.ehDengue ? "acima" : "abaixo"} do limiar de{" "}
                  {LIMIAR_DENGUE}%
                </small>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default PredictionSimulator;
