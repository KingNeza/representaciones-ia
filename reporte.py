"""Reporte: cuenta la codificación HUMANA por condición. El modelo no cuenta nada.

Genera:
  salidas/reporte.xlsx   una hoja por categoría (denominación × escenario) + contraste A3
  salidas/resumen.md     las mismas tablas en texto
"""
from pathlib import Path

import pandas as pd

from codificacion import HOJA, cargar_codebook

RAIZ = Path(__file__).parent
SALIDAS = RAIZ / "salidas"
ORDEN_DEN = ["(sin denominación)", "indígena", "mestiza", "blanca"]


def _tabla(df: pd.DataFrame, col: str) -> pd.DataFrame:
    t = pd.crosstab([df["escenario"], df["denominacion"]], df[col])
    orden = [(e, d) for e in df["escenario"].unique() for d in ORDEN_DEN if (e, d) in t.index]
    return t.reindex(orden)


def generar_reporte():
    print("[R] Reporte")
    SALIDAS.mkdir(exist_ok=True)
    if not HOJA.exists():
        raise SystemExit("No existe la hoja de codificación. Corre primero la etapa `codificar`.")
    df = pd.read_excel(HOJA, sheet_name="codificacion")
    cats = cargar_codebook()
    codificadas = df.dropna(subset=[c["id"] for c in cats], how="all")
    lineas = ["# Resumen de la codificación", "",
              f"Imágenes en la hoja: **{len(df)}** · codificadas: **{len(codificadas)}**", ""]
    if codificadas.empty:
        print("  (todavía no hay imágenes codificadas en la hoja)")

    with pd.ExcelWriter(SALIDAS / "reporte.xlsx", engine="openpyxl") as w:
        for c in cats:
            if c["id"] not in codificadas or codificadas[c["id"]].dropna().empty:
                continue
            datos = codificadas.dropna(subset=[c["id"]]).copy()
            if c["tipo"] == "varias":   # "rebozo; talavera" -> dos filas
                datos[c["id"]] = datos[c["id"]].astype(str).str.split(";")
                datos = datos.explode(c["id"]).reset_index(drop=True)
                datos[c["id"]] = datos[c["id"]].str.strip()
            t = _tabla(datos, c["id"])
            t.to_excel(w, sheet_name=c["id"][:31])
            nota = " (una imagen puede tener varios)" if c["tipo"] == "varias" else ""
            lineas += [f"## {c['nombre']}{nota}", "", t.to_markdown(), ""]

        contraste = RAIZ / "registro" / "a3_contraste.csv"
        if contraste.exists():
            a3 = pd.read_csv(contraste, encoding="utf-8-sig")
            t = pd.crosstab(a3["requisito"], a3["estado"])
            t.to_excel(w, sheet_name="A3_contraste")
            lineas += ["## Contraste visual (A3) · estados por requisito", "", t.to_markdown(), ""]
        if not w.book.sheetnames:
            pd.DataFrame({"aviso": ["sin datos codificados"]}).to_excel(w, sheet_name="vacio", index=False)

    (SALIDAS / "resumen.md").write_text("\n".join(lineas), encoding="utf-8")
    print("  → salidas/reporte.xlsx, salidas/resumen.md")
