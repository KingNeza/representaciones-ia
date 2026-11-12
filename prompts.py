"""Construcción de prompts a partir de la plantilla aprobada. SIN modelo de lenguaje.

Como señala el propio protocolo: una vez aprobada la plantilla, la sustitución de términos
y la producción de combinaciones se hacen por programación. Así se cumplen R1 y R3 por
construcción: nadie (ni humano ni agente) reescribe los prompts uno por uno.
"""
from pathlib import Path

import yaml

RAIZ = Path(__file__).parent


def cargar_protocolo() -> dict:
    with open(RAIZ / "protocolo.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def condiciones(protocolo: dict) -> list[dict]:
    """C01–C08: escenario por fuera, denominación por dentro (como la tabla del documento P3)."""
    filas, n = [], 1
    for clave_esc, texto_esc in protocolo["escenarios"].items():
        for denominacion in protocolo["denominaciones"]:
            prompt = protocolo["plantilla"].format(denominacion=denominacion, escenario=texto_esc)
            filas.append({
                "condicion": f"C{n:02d}",
                "denominacion": denominacion.strip() or "(sin denominación)",
                "escenario": clave_esc,
                "prompt": prompt,
            })
            n += 1
    return filas


def lote(protocolo: dict) -> list[dict]:
    """Una fila por imagen: condición × repetición, con su semilla."""
    filas = []
    for c in condiciones(protocolo):
        for r in range(1, protocolo["repeticiones"] + 1):
            semilla = protocolo["semilla_base"] + r      # misma semilla en todas las condiciones
            filas.append({**c, "repeticion": r, "semilla": semilla,
                          "id_imagen": f"{c['condicion']}_r{r:02d}_s{semilla}",
                          "version_protocolo": protocolo["version"]})
    return filas


if __name__ == "__main__":
    for c in condiciones(cargar_protocolo()):
        print(c["condicion"], "|", c["prompt"])
