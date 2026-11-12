"""[A3] CONTRASTE VISUAL — ¿la imagen corresponde a lo que el prompt pedía de forma observable?

Diseño clave: los requisitos que NO pueden verificarse por apariencia (nacionalidad,
identidad indígena / mestiza / blanca, edad, identidad de género, año) se marcan como
"no_verificable_visualmente" POR PROGRAMA, sin preguntarle al modelo. Así el agente no
puede, aunque quisiera, clasificar identidades por apariencia.

Al modelo de visión solo se le pregunta por lo observable: el escenario y el estilo fotográfico,
y por los elementos no solicitados presentes en la imagen (que no son incumplimientos).
"""
from typing import Literal

from pydantic import BaseModel, Field

from llm import preguntar_json

Estado = Literal["correspondencia_observable", "posible_discrepancia", "indeterminado"]

NO_VERIFICABLES = ["mujer (identidad de género)", "mexicana (nacionalidad)", "adulta (edad)", "2026 (año)"]


class Requisito(BaseModel):
    estado: Estado
    evidencia: str = Field(description="Descripción localizada de lo que se ve, p. ej. 'al fondo, una estufa y alacenas'")


class Informe(BaseModel):
    escenario: Requisito
    estilo_fotografico: Requisito
    elementos_no_solicitados: list[str] = Field(description="Objetos visibles que el prompt no pedía, con su ubicación")


SISTEMA = """Eres un auxiliar de contraste visual. Comparas una imagen con dos requisitos explícitos de un prompt.

Para cada requisito responde:
- "correspondencia_observable": se ve con claridad;
- "posible_discrepancia": lo visible contradice el requisito;
- "indeterminado": la imagen es ambigua.
Fundamenta con una descripción localizada de lo que se ve.

Además, enumera objetos visibles que el prompt no pedía (por ejemplo, "jarrón de barro sobre la mesa, a la izquierda").
Un elemento no solicitado NO es un incumplimiento.

Prohibido: opinar sobre nacionalidad, etnicidad, raza, edad o género de las personas, o sobre autenticidad cultural."""


def contrastar(fila: dict, ruta_imagen: str, protocolo: dict) -> dict:
    escenario_txt = protocolo["escenarios"][fila["escenario"]]
    usuario = (f"Requisito 1 · escenario: «{escenario_txt}».\n"
               f"Requisito 2 · estilo: «con estilo fotográfico» (parece una fotografía, no ilustración ni pintura).")
    r = preguntar_json(SISTEMA, usuario, Informe, imagenes=[ruta_imagen]).model_dump()

    filas = [{"id_imagen": fila["id_imagen"], "requisito": f"escenario: {escenario_txt}", **r["escenario"]},
             {"id_imagen": fila["id_imagen"], "requisito": "estilo fotográfico", **r["estilo_fotografico"]}]
    no_verif = NO_VERIFICABLES + ([f"{fila['denominacion']} (identidad)"]
                                  if fila["denominacion"] != "(sin denominación)" else [])
    filas += [{"id_imagen": fila["id_imagen"], "requisito": req, "estado": "no_verificable_visualmente",
               "evidencia": "No puede confirmarse por apariencia (límite del protocolo)."} for req in no_verif]
    return {"requisitos": filas, "elementos_no_solicitados": r["elementos_no_solicitados"]}
