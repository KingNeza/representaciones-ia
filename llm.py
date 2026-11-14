"""Puente único con los modelos de lenguaje: Ollama (local) o pollinations.ai (por internet).

Todos los agentes hablan con el modelo a través de `preguntar_json`.
"""
import json
import os
import time
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

RAIZ = Path(__file__).parent
with open(RAIZ / "config.yaml", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Modo simulado: permite probar el flujo completo sin Ollama ni generador de imágenes.
SIMULAR = os.environ.get("REPRESENTACIONES_SIMULAR") == "1"


def describir_modelo(vision: bool = False) -> str:
    if CONFIG.get("llm_via", "ollama") == "pollinations":
        return f"pollinations · {CONFIG.get('modelo_vision_pollinations' if vision else 'modelo_texto_pollinations', 'openai')}"
    return CONFIG["modelo_vision" if vision else "modelo_texto"]


def preguntar_json(sistema: str, usuario: str, esquema: type[BaseModel],
                   imagenes: list[str] | None = None, reintentos: int = 2) -> BaseModel:
    """Envía un prompt (y opcionalmente imágenes) y obliga al modelo a responder con el esquema dado."""
    if SIMULAR:
        from simulador import respuesta_simulada
        return esquema.model_validate(respuesta_simulada(esquema, usuario))
    if CONFIG.get("llm_via", "ollama") == "pollinations":
        return _preguntar_pollinations(sistema, usuario, esquema, imagenes, reintentos)

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



# ---------------- Vía alternativa: pollinations.ai (sin Ollama) ----------------
def _imagen_como_data_uri(ruta: str) -> str:
    """Convierte la imagen a JPEG en memoria y la codifica para enviarla dentro del mensaje."""
    import base64
    import io
    from PIL import Image
    img = Image.open(ruta).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _extraer_json(texto: str) -> str:
    """Algunos modelos envuelven el JSON en ```json ... ```: se quita el envoltorio."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[1] if "\n" in texto else texto[3:]
        texto = texto.rsplit("```", 1)[0]
    inicio, fin = texto.find("{"), texto.rfind("}")
    return texto[inicio:fin + 1] if inicio != -1 and fin != -1 else texto


def _preguntar_pollinations(sistema, usuario, esquema, imagenes, reintentos):
    import requests
    from generador import _clave

    modelo = CONFIG.get("modelo_vision_pollinations" if imagenes else "modelo_texto_pollinations", "openai")
    # Sin esquema obligatorio en el servidor: se describe en el mensaje y se valida aquí con pydantic.
    sistema_json = (sistema + "\n\nResponde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, "
                    "que cumpla este esquema JSON:\n" + json.dumps(esquema.model_json_schema(), ensure_ascii=False))
    contenido = [{"type": "text", "text": usuario}]
    for ruta in imagenes or []:
        contenido.append({"type": "image_url", "image_url": {"url": _imagen_como_data_uri(ruta)}})
    cuerpo = {"model": modelo,
              "messages": [{"role": "system", "content": sistema_json},
                           {"role": "user", "content": contenido if imagenes else usuario}],
              "temperature": CONFIG.get("temperatura", 0.2),
              "response_format": {"type": "json_object"}}
    cabeceras = {"Authorization": f"Bearer {_clave('pollinations')}"}

    ultimo_error = None
    for intento in range(reintentos + 1):
        r = requests.post("https://gen.pollinations.ai/v1/chat/completions", json=cuerpo,
                          headers=cabeceras, timeout=180)
        if r.status_code == 400 and ("temperature" in cuerpo or "response_format" in cuerpo):
            # Algunos modelos no aceptan esos parámetros: se reintenta sin ellos.
            cuerpo.pop("temperature", None)
            cuerpo.pop("response_format", None)
            continue
        if r.status_code == 429:
            time.sleep(20 * (intento + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"pollinations (texto) respondió {r.status_code}: {r.text[:300]}")
        try:
            texto = r.json()["choices"][0]["message"]["content"] or ""
            return esquema.model_validate_json(_extraer_json(texto))
        except (ValidationError, json.JSONDecodeError, KeyError, IndexError) as e:
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
