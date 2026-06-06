import { useState } from "react";
import CheckboxItem from "../components/CheckboxItem";
import Resultado from "../components/Resultado";
import { avaliarDengue, symptoms } from "../services/dengueRules";

function Home() {
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);

  function toggleSymptom(id: string) {
    setSelectedSymptoms((current) => {
      if (current.includes(id)) {
        return current.filter((item) => item !== id);
      }

      return [...current, id];
    });
  }

  const resultado = avaliarDengue(selectedSymptoms);

  return (
    <main className="container">
      <section className="card">
        <h1>Triagem de Dengue</h1>

        <p>
          Marque os sintomas que você está sentindo. O sistema vai indicar se há
          baixa, moderada ou alta suspeita de dengue.
        </p>

        <div className="checkbox-list">
          {symptoms.map((symptom) => (
            <CheckboxItem
              key={symptom.id}
              label={symptom.label}
              checked={selectedSymptoms.includes(symptom.id)}
              onChange={() => toggleSymptom(symptom.id)}
            />
          ))}
        </div>

        <Resultado
          title={resultado.title}
          message={resultado.message}
          level={resultado.level}
          points={resultado.points}
        />
      </section>
    </main>
  );
}

export default Home;