"""Acuerdo entre dos codificadoras (kappa de Cohen) para una categoría del libro de códigos.

Procedimiento:
1. Copia codificacion/codificacion_imagenes.xlsx como, por ejemplo, codificacion_segunda.xlsx
   y pide a una segunda persona que codifique ahí, sin ver tu codificación.
2. Corre:
   python validacion/kappa.py codificacion/codificacion_imagenes.xlsx codificacion/codificacion_segunda.xlsx ESCENARIO

Lectura orientativa (Landis y Koch): <0.40 débil · 0.41–0.60 moderado ·
0.61–0.80 sustancial · >0.80 casi perfecto.
"""
import sys
from collections import Counter

import pandas as pd


def kappa_cohen(a: list, b: list) -> float:
    n = len(a)
    observado = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    esperado = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if esperado == 1 else (observado - esperado) / (1 - esperado)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    a_ruta, b_ruta, cat = sys.argv[1:]
    a = pd.read_excel(a_ruta, sheet_name="codificacion")[["id_imagen", cat]]
    b = pd.read_excel(b_ruta, sheet_name="codificacion")[["id_imagen", cat]]
    df = a.merge(b, on="id_imagen", suffixes=("_1", "_2")).dropna()
    if df.empty:
        sys.exit("No hay imágenes codificadas por ambas personas en esa categoría.")
    x = df[f"{cat}_1"].astype(str).str.strip().tolist()
    y = df[f"{cat}_2"].astype(str).str.strip().tolist()
    print(f"Categoría:        {cat}")
    print(f"Imágenes:         {len(df)}")
    print(f"Acuerdo simple:   {sum(i == j for i, j in zip(x, y)) / len(x):.0%}")
    print(f"Kappa de Cohen:   {kappa_cohen(x, y):.2f}")
    print("\nCoincidencias y discrepancias (filas = codificadora 1, columnas = codificadora 2):")
    print(pd.crosstab(pd.Series(x, name="1"), pd.Series(y, name="2")))
