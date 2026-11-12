"""[A2] REVISOR DE CORRESPONDENCIA — ¿cada prompt conserva las decisiones del protocolo?

Dos capas:
  1. Comprobación determinista (sin modelo): ¿aparecen literalmente la denominación y el escenario?
  2. Revisión semántica (con modelo): ¿hay atributos añadidos o cambios de sentido?
     Una búsqueda de palabras no basta: "blanca" puede describir una prenda o a la figura.

No recibe la justificación de A1 (comprobación separada). "compatible" solo significa que
no encontró conflictos; la aprobación es de la investigadora (R6).
"""
from typing import Literal

from pydantic import BaseModel, Field

from llm import preguntar_json


class Observacion(BaseModel):
    regla: str = Field(description="Id de la regla involucrada, por ejemplo R2")
    fragmento: str = Field(description="Fragmento literal del prompt al que se refiere")
    explicacion: str


class Informe(BaseModel):
    estado: Literal["compatible", "requiere_revision", "indeterminado"]
    observaciones: list[Observacion]


SISTEMA = """Eres un auxiliar de revisión metodológica. Comparas un prompt con las reglas de un protocolo de investigación.

Reglas:
{reglas}

Devuelve:
- "compatible" si no encuentras conflictos con las reglas;
- "requiere_revision" si detectas omisiones, atributos añadidos sin autorización o cambios de sentido;
- "indeterminado" si no puedes decidir.
Cada observación debe citar el fragmento literal del prompt y la regla involucrada.
No juzgues la calidad estética ni la autenticidad cultural."""


def comprobar_literal(fila: dict, protocolo: dict) -> list[str]:
    faltas = []
    esc = protocolo["escenarios"][fila["escenario"]]
    if esc not in fila["prompt"]:
        faltas.append(f"R1: falta el escenario «{esc}»")
    den = fila["denominacion"]
    if den != "(sin denominación)" and den not in fila["prompt"]:
        faltas.append(f"R1: falta la denominación «{den}»")
    return faltas


def revisar(fila: dict, protocolo: dict) -> dict:
    faltas = comprobar_literal(fila, protocolo)
    reglas = "\n".join(f"{k}. {v}" for k, v in protocolo["reglas"].items())
    usuario = (f"Condición solicitada por la investigadora: denominación = {fila['denominacion']}; "
               f"escenario = {protocolo['escenarios'][fila['escenario']]}.\n"
               f"Prompt a revisar: \"{fila['prompt']}\"")
    informe = preguntar_json(SISTEMA.format(reglas=reglas), usuario, Informe).model_dump()
    if faltas:   # la comprobación literal manda sobre el modelo
        informe["estado"] = "requiere_revision"
        informe["observaciones"] += [{"regla": "R1", "fragmento": "", "explicacion": f} for f in faltas]
    return informe
