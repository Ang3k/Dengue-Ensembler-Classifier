type ModelResult = {
  name: string;
  result: string;
  confidence: string;
  description: string;
};

type ResultadoProps = {
  title: string;
  message: string;
  level: string;
  models: {
    clinical: ModelResult;
    epidemiological: ModelResult;
  };
};

function Resultado({ title, message, level, models }: ResultadoProps) {
  return (
    <div className={`resultado resultado-${level.toLowerCase()}`}>
      <h2>{title}</h2>

      <p>{message}</p>

      <div className="avaliacoes-container">
        <div className="avaliacao-card">
          <h3>Modelo 1</h3>
          <span className="avaliacao-status">{models.clinical.result}</span>
          <p>{models.clinical.description}</p>
        </div>

        <div className="avaliacao-card">
          <h3>Modelo 2</h3>
          <span className="avaliacao-status">
            {models.epidemiological.result}
          </span>
          <p>{models.epidemiological.description}</p>
        </div>
      </div>

      <div className="orientacao-final">
        <strong>Orientação:</strong>
        <p>
          Esta triagem é apenas informativa e não substitui avaliação médica.
          Em caso de piora, febre persistente, sangramentos, dor abdominal
          intensa, vômitos persistentes ou sonolência, procure atendimento em
          uma unidade de saúde.
        </p>
      </div>
    </div>
  );
}

export default Resultado;