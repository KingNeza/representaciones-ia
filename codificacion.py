"""Hoja de codificación humana (R8): un Excel con una fila por imagen, su miniatura y
listas desplegables con los valores del libro de códigos.

La investigadora llena las columnas de cada categoría y la columna `memo`.
Si la hoja ya existe, NO se sobrescribe: solo se agregan las imágenes nuevas.
"""
from pathlib import Path

import pandas as pd
import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

RAIZ = Path(__file__).parent
HOJA = RAIZ / "codificacion" / "codificacion_imagenes.xlsx"
MINIS = RAIZ / "codificacion" / "miniaturas"
FIJAS = ["id_imagen", "condicion", "denominacion", "escenario", "repeticion", "semilla", "miniatura"]


def cargar_codebook() -> list[dict]:
    with open(RAIZ / "codebook_visual.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["categorias"]


def _miniatura(ruta: Path, lado: int = 150) -> Path:
    from PIL import Image
    MINIS.mkdir(parents=True, exist_ok=True)
    destino = MINIS / f"{ruta.stem}.png"
    if not destino.exists():
        img = Image.open(ruta)
        img.thumbnail((lado, lado))
        img.save(destino)
    return destino


def preparar_hoja(generaciones: pd.DataFrame):
    cats = cargar_codebook()
    columnas = FIJAS + [c["id"] for c in cats] + ["memo"]
    ok = generaciones[generaciones["estado"] == "ok"]

    if HOJA.exists():
        wb = load_workbook(HOJA)
        ws = wb["codificacion"]
        ya = {ws.cell(row=i, column=1).value for i in range(2, ws.max_row + 1)}
        # Si al abrir el Excel se perdieron las miniaturas, se vuelven a colocar.
        for i in (range(2, ws.max_row + 1) if not ws._images else []):
            mini = MINIS / f"{ws.cell(row=i, column=1).value}.png"
            if mini.exists():
                ws.add_image(XLImage(str(mini)), f"G{i}")
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "codificacion"
        ws.append(columnas)
        for celda in ws[1]:
            celda.font = Font(bold=True)
            celda.fill = PatternFill("solid", fgColor="EEEEEE")
        ws.freeze_panes = "H2"
        for i, col in enumerate(columnas, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = (
                22 if col == "miniatura" else 40 if col == "memo" else 18)
        # Listas desplegables para las categorías de un solo valor
        for c in cats:
            if c["tipo"] == "una":
                letra = ws.cell(row=1, column=columnas.index(c["id"]) + 1).column_letter
                dv = DataValidation(type="list", formula1='"' + ",".join(map(str, c["valores"])) + '"',
                                    allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(f"{letra}2:{letra}5000")
        # Hoja de instrucciones con las definiciones
        ins = wb.create_sheet("instrucciones")
        ins.append(["categoría", "tipo", "definición", "valores permitidos"])
        for c in cats:
            ins.append([f"{c['id']} — {c['nombre']}",
                        "un valor (lista)" if c["tipo"] == "una" else "varios, separados por ;",
                        " ".join(c["definicion"].split()), ", ".join(map(str, c["valores"]))])
        for col, w in zip("ABCD", (30, 22, 70, 70)):
            ins.column_dimensions[col].width = w
        for fila in ins.iter_rows():
            for celda in fila:
                celda.alignment = Alignment(wrap_text=True, vertical="top")
        ya = set()

    nuevas = 0
    for _, g in ok.iterrows():
        if g["id_imagen"] in ya:
            continue
        ws.append([g["id_imagen"], g["condicion"], g["denominacion"], g["escenario"],
                   int(g["repeticion"]), int(g["semilla"]), ""] + [""] * (len(cats) + 1))
        fila = ws.max_row
        ws.row_dimensions[fila].height = 118
        img = XLImage(str(_miniatura(RAIZ / g["archivo"])))
        ws.add_image(img, f"G{fila}")
        celda = ws.cell(row=fila, column=1)
        celda.hyperlink = str((RAIZ / g["archivo"]).resolve())   # clic: abre la imagen completa
        celda.font = Font(color="0563C1", underline="single")
        nuevas += 1
    HOJA.parent.mkdir(exist_ok=True)
    wb.save(HOJA)
    print(f"  → {HOJA.relative_to(RAIZ)}  ({nuevas} imágenes nuevas para codificar)")
