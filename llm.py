"""Puente único con los modelos locales de Ollama (texto y visión).

Todos los agentes hablan con el modelo a través de `preguntar_json`.
"""
import json
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

RAIZ = Path(__file__).parent
with open(RAIZ / "config.yaml", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Modo simulado: permite probar el flujo completo sin Ollama ni generador de imágenes.
SIMULAR = os.environ.get("REPRESENTACIONES_SIMULAR") == "1"


def preguntar_json(sistema: str, usuario: str, esquema: type[BaseModel],
                   imagenes: list[str] | None = None, reintentos: int = 2) -> BaseModel:
    """Envía un prompt (y opcionalmente imágenes) y obliga al modelo a responder con el esquema dado."""
    if SIMULAR:
        from simulador import respuesta_simulada
        return esquema.model_validate(respuesta_simulada(esquema, usuario))

    import ollama

    mensaje = {"role": "user", "content": usuario}
    if imagenes:
        mensaje["images"] = [str(p) for p in imagenes]
    kwargs = dict(
        model=CONFIG["modelo_vision"] if imagenes else CONFIG["modelo_texto"],
        messages=[{"role": "system", "content": sistema}, mensaje],
        format=esquema.model_json_schema(),
        options={
            "temperature": CONFIG.get("temperatura", 0.2),
            "repeat_penalty": 1.15,   # castiga repetir lo mismo (evita ciclos)
            "num_predict": 2048,      # tope de longitud: nunca se queda colgado
        },
    )
    if CONFIG.get("desactivar_razonamiento"):
        kwargs["think"] = False

    ultimo_error = None
    for intento in range(reintentos + 1):
        try:
            try:
                r = ollama.chat(**kwargs)
            except ollama.ResponseError as e:
                if "think" in str(e).lower() and "think" in kwargs:   # modelo sin modo de razonamiento
                    kwargs.pop("think")
                    r = ollama.chat(**kwargs)
                else:
                    raise
            return esquema.model_validate_json(r["message"]["content"])
        except (ValidationError, json.JSONDecodeError) as e:
            ultimo_error = e
            print(f"  ⚠ respuesta inválida (intento {intento + 1}), reintentando...")
    raise RuntimeError(f"El modelo no devolvió JSON válido tras {reintentos + 1} intentos: {ultimo_error}")


if __name__ == "__main__":
    import sys

    class Descripcion(BaseModel):
        espacio: str
        objetos_visibles: list[str]

    if len(sys.argv) > 1:   # python llm.py ruta/a/imagen.png  -> prueba el modelo de visión
        print(preguntar_json("Responde solo en JSON, en español. Describe solo lo visible.",
                             "¿Qué tipo de espacio aparece y qué objetos son visibles?",
                             Descripcion, imagenes=[sys.argv[1]]))
    else:                   # python llm.py  -> prueba el modelo de texto
        class Respuesta(BaseModel):
            concepto: str
            definicion: str
        print(preguntar_json("Responde solo en JSON, en español.",
                             "Define en una frase qué es una representación algorítmica.", Respuesta))
