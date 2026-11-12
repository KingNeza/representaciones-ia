"""Respuestas falsas para probar el flujo sin Ollama:
    REPRESENTACIONES_SIMULAR=1 python pipeline.py

Útil para revisar la "plomería". NO produce análisis real.
"""
import random

random.seed(0)


def respuesta_simulada(esquema, usuario: str) -> dict:
    nombre = esquema.__name__
    if nombre == "Propuesta":
        return {"ambiguedades": ["(simulado) «espacio de trabajo» admite oficina, campo o comercio"],
                "decisiones_faltantes": ["(simulado) ¿una sola figura o varias?"],
                "alternativas": ["(simulado) Fotografía de una mujer mexicana adulta{denominacion} {escenario}, en 2026."],
                "cambios_respecto_de_la_plantilla": ["(simulado) elimina «Genera una imagen de»"],
                "preguntas_para_la_investigadora": ["(simulado) ¿Se conserva la fórmula conversacional?"]}
    if "estilo_fotografico" in esquema.model_fields:          # A3
        estados = ["correspondencia_observable", "posible_discrepancia", "indeterminado"]
        req = lambda: {"estado": random.choice(estados), "evidencia": "(simulado)"}
        return {"escenario": req(), "estilo_fotografico": req(),
                "elementos_no_solicitados": random.sample(["planta", "taza", "ventana", "rebozo"], k=2)}
    if nombre == "Informe":
        return {"estado": "compatible", "observaciones": []}
    return {}
