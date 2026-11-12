"""[A1] FORMULADOR — revisa la plantilla del protocolo ANTES de aprobarla.

No reescribe el protocolo: propone, señala ambigüedades y pregunta (R4).
La investigadora decide y, si acepta algo, lo cambia ella misma en protocolo.yaml (R5).
"""
from pydantic import BaseModel, Field

from llm import preguntar_json


class Propuesta(BaseModel):
    ambiguedades: list[str] = Field(description="Términos o decisiones de la plantilla que admiten más de una lectura")
    decisiones_faltantes: list[str] = Field(description="Información indispensable que el protocolo no define")
    alternativas: list[str] = Field(description="Otras redacciones posibles que conserven exactamente las mismas condiciones")
    cambios_respecto_de_la_plantilla: list[str] = Field(description="Para cada alternativa, qué modifica respecto de la plantilla")
    preguntas_para_la_investigadora: list[str]


SISTEMA = """Eres un auxiliar de formulación de instrucciones para una investigación sobre representaciones
de mujeres mexicanas en imágenes generativas. Tu tarea es examinar una plantilla de prompt.

Reglas que NO puedes romper:
{reglas}

Límites: no añadas por iniciativa propia rasgos físicos, vestimentas, profesiones, relaciones familiares ni
posiciones sociales. No establezcas qué apariencia corresponde a una mujer indígena, mestiza o blanca.
Si falta información indispensable, pregunta; no la supongas."""


def revisar_plantilla(protocolo: dict) -> dict:
    reglas = "\n".join(f"{k}. {v}" for k, v in protocolo["reglas"].items())
    usuario = (f"Plantilla: {protocolo['plantilla']}\n"
               f"Valores de {{denominacion}}: {protocolo['denominaciones']}\n"
               f"Valores de {{escenario}}: {list(protocolo['escenarios'].values())}\n"
               f"Idioma: {protocolo['idioma']}")
    return preguntar_json(SISTEMA.format(reglas=reglas), usuario, Propuesta).model_dump()
