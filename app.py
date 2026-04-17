from flask import Flask, request, jsonify, send_from_directory
import os
import json
from openai import OpenAI

app = Flask(__name__, static_folder=".")

client = OpenAI()

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/generar_pregunta", methods=["POST"])
def generar_pregunta():
    data = request.json
    puesto = data.get("puesto", "")
    historial = data.get("historial", [])

    historial_texto = ""
    if historial:
        historial_texto = "\n\nPreguntas ya realizadas (no repetir):\n" + "\n".join(f"- {p}" for p in historial)

    prompt = f"""Eres un entrevistador experto de recursos humanos. El candidato aplica al puesto: "{puesto}".
{historial_texto}

Genera UNA sola pregunta de entrevista laboral relevante para ese puesto. 
La pregunta debe ser directa, profesional y diferente a las ya realizadas.
Responde SOLO con la pregunta, sin numeración ni explicación adicional."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.8
    )

    pregunta = response.choices[0].message.content.strip()
    return jsonify({"pregunta": pregunta})


@app.route("/preguntas_sugeridas", methods=["POST"])
def preguntas_sugeridas():
    data = request.json
    puesto = data.get("puesto", "")

    prompt = f"""Eres un entrevistador experto. El candidato aplica al puesto: "{puesto}".

Genera exactamente 5 preguntas de entrevista variadas y relevantes para ese puesto.
Cubre diferentes áreas: motivación, experiencia, habilidades técnicas, situaciones difíciles y trabajo en equipo.

Responde en formato JSON con esta estructura exacta:
{{
  "preguntas": [
    "Pregunta 1",
    "Pregunta 2",
    "Pregunta 3",
    "Pregunta 4",
    "Pregunta 5"
  ]
}}"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.7
    )

    content = response.choices[0].message.content.strip()
    try:
        data_json = json.loads(content)
        return jsonify(data_json)
    except:
        return jsonify({"preguntas": [content]})


@app.route("/evaluar", methods=["POST"])
def evaluar():
    data = request.json
    puesto = data.get("puesto", "")
    pregunta = data.get("pregunta", "")
    respuesta = data.get("respuesta", "")
    historial_respuestas = data.get("historial_respuestas", [])

    historial_texto = ""
    if historial_respuestas:
        historial_texto = "\n\nRespuestas anteriores del candidato:\n" + "\n".join(
            f"- P: {item['pregunta']}\n  R: {item['respuesta']}" for item in historial_respuestas[-3:]
        )

    prompt = f"""Eres un evaluador experto de recursos humanos. Analiza la siguiente respuesta de entrevista.

Puesto al que aplica: {puesto}
Pregunta realizada: {pregunta}
Respuesta del candidato: {respuesta}
{historial_texto}

Evalúa la respuesta y responde en formato JSON con esta estructura exacta:
{{
  "feedback": "Retroalimentación detallada sobre la respuesta (2-3 oraciones)",
  "que_le_falta": "Qué elementos específicos le faltan a la respuesta para ser excelente",
  "puntos_fuertes": "Qué hizo bien el candidato en esta respuesta",
  "preguntas_relacionadas": [
    "Pregunta de seguimiento relacionada 1",
    "Pregunta de seguimiento relacionada 2",
    "Pregunta de seguimiento relacionada 3"
  ],
  "probabilidad": 75,
  "justificacion_probabilidad": "Breve explicación del porcentaje asignado",
  "consejo": "Un consejo concreto para mejorar la respuesta"
}}

El campo "probabilidad" debe ser un número entero del 0 al 100 que represente la probabilidad estimada de que el candidato consiga el empleo basándose en TODAS sus respuestas hasta ahora.
Sé honesto pero constructivo."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.5
    )

    content = response.choices[0].message.content.strip()
    try:
        result = json.loads(content)
        return jsonify(result)
    except:
        return jsonify({
            "feedback": content,
            "que_le_falta": "No se pudo analizar.",
            "puntos_fuertes": "",
            "preguntas_relacionadas": [],
            "probabilidad": 50,
            "justificacion_probabilidad": "",
            "consejo": ""
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=False)
