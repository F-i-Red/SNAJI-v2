
import { useState } from "react";
import axios from "axios";

export default function CaseUpload() {

  const [texto, setTexto] = useState("");
  const [resultado, setResultado] = useState<any>(null);

  async function enviarCaso() {

    const response = await axios.post(
      "http://localhost:8000/analysis",
      { texto }
    );

    setResultado(response.data);
  }

  return (
    <div>
      <h2>Submissão de Caso</h2>

      <textarea
        rows={10}
        cols={100}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
      />

      <br />

      <button onClick={enviarCaso}>
        Analisar
      </button>

      {resultado && (
        <pre>
          {JSON.stringify(resultado, null, 2)}
        </pre>
      )}
    </div>
  );
}
