type ResultadoProps = {
  title: string;
  message: string;
  level: string;
  points: number;
};

function Resultado({ title, message, level, points }: ResultadoProps) {
  return (
    <div className={`resultado resultado-${level.toLowerCase()}`}>
      <h2>{title}</h2>
      <p>{message}</p>
      <p>
        <strong>Pontuação:</strong> {points}
      </p>

      <small>
        Este resultado é apenas uma triagem educativa e não substitui avaliação
        médica.
      </small>
    </div>
  );
}

export default Resultado;