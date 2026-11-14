"""Orquestador del equipo de agentes auxiliares.

Uso:
    python pipeline.py --etapa formular     # A1 revisa la plantilla (antes de aprobar)
    python pipeline.py --etapa prompts      # arma el lote de prompts (sin modelo)
    python pipeline.py --etapa revisar      # A2 revisa cada prompt contra las reglas
    python pipeline.py --etapa generar      # genera las imágenes (exige aprobación, R6)
    python pipeline.py --etapa contrastar   # A3 contrasta prompt e imagen
    python pipeline.py --etapa codificar    # prepara la hoja de Excel para la investigadora
    python pipeline.py --etapa reporte      # cuenta la codificación humana por condición
    python pipeline.py                      # todas, en ese orden
    python pipeline.py --etapa generar --limite 4   # solo 4 imágenes (para probar)

Todo queda registrado en registro/ (R5, R7).
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from llm import CONFIG, SIMULAR
from prompts import cargar_protocolo, lote

RAIZ = Path(__file__).parent
REG = RAIZ / "registro"
IMG = RAIZ / "imagenes"
REG.mkdir(exist_ok=True)
IMG.mkdir(exist_ok=True)


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def etapa_formular(_):
    from agentes.formulador import revisar_plantilla
    print(f"[A1] Formulador  (modelo: {CONFIG['modelo_texto']})")
    p = cargar_protocolo()
    r = revisar_plantilla(p)
    r.update({"version_protocolo": p["version"], "fecha": ahora(), "autoria": "A1"})
    destino = REG / f"a1_propuesta_{p['version']}.json"
    destino.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    for clave in ["ambiguedades", "decisiones_faltantes", "preguntas_para_la_investigadora"]:
        for x in r[clave]:
            print(f"  · {clave.replace('_', ' ')}: {x}")
    print(f"  → {destino.relative_to(RAIZ)}   (A1 no modifica el protocolo: decide la investigadora)")


def etapa_prompts(_):
    print("[P] Lote de prompts (sin modelo)")
    p = cargar_protocolo()
    filas = lote(p)
    pd.DataFrame(filas).to_csv(REG / "prompts.csv", index=False, encoding="utf-8-sig")
    print(f"  → {len(filas)} imágenes previstas ({len(filas) // p['repeticiones']} condiciones × "
          f"{p['repeticiones']} repeticiones) en registro/prompts.csv")


def etapa_revisar(_):
    from agentes.revisor import revisar
    print(f"[A2] Revisor  (modelo: {CONFIG['modelo_texto']})")
    p = cargar_protocolo()
    unicos = pd.read_csv(REG / "prompts.csv", encoding="utf-8-sig").drop_duplicates("condicion")
    filas = []
    for _, f in unicos.iterrows():
        inf = revisar(f.to_dict(), p)
        print(f"  · {f['condicion']}: {inf['estado']}")
        for o in inf["observaciones"]:
            print(f"      {o['regla']}: {o['explicacion']}")
        filas.append({"condicion": f["condicion"], "prompt": f["prompt"], "estado": inf["estado"],
                      "observaciones": json.dumps(inf["observaciones"], ensure_ascii=False),
                      "version_protocolo": p["version"], "fecha": ahora()})
    pd.DataFrame(filas).to_csv(REG / "a2_revision.csv", index=False, encoding="utf-8-sig")
    print("  → registro/a2_revision.csv   ('compatible' no es aprobación: decide la investigadora)")


def etapa_generar(args):
    p = cargar_protocolo()
    ap = p.get("aprobacion", {})
    if not (ap.get("aprobado") and ap.get("por") and ap.get("fecha")):
        sys.exit("✋ R6: el protocolo no está aprobado. Revisa registro/a2_revision.csv y, si estás de acuerdo,\n"
                 "   llena `aprobacion` en protocolo.yaml (aprobado: true, por, fecha).")
    from generador import describir_via, generar_imagen
    g = CONFIG["generador"]
    print(f"[G] Generación  ({describir_via()}, {g['ancho']}×{g['alto']})")
    plan = pd.read_csv(REG / "prompts.csv", encoding="utf-8-sig")
    ruta_reg = REG / "generaciones.csv"
    previas = pd.read_csv(ruta_reg, encoding="utf-8-sig") if ruta_reg.exists() else pd.DataFrame(columns=["id_imagen", "estado"])
    ok_prev = previas[previas["estado"] == "ok"]
    # "ya generada" = registrada como ok Y con su archivo presente en imagenes/
    hechas = {i for i, a in zip(ok_prev["id_imagen"], ok_prev.get("archivo", [])) if (RAIZ / str(a)).exists()}
    pendientes = plan[~plan["id_imagen"].isin(hechas)]
    if args.limite:
        pendientes = pendientes.head(args.limite)
    print(f"  {len(hechas)} ya generadas · {len(pendientes)} por generar")
    for _, f in pendientes.iterrows():
        destino = IMG / f"{f['id_imagen']}.png"
        intento = {**f.to_dict(), "archivo": str(destino.relative_to(RAIZ)), "via": describir_via(),
                   "ancho": g["ancho"], "alto": g["alto"], "pasos": g["pasos"],
                   "aprobado_por": ap["por"], "fecha": ahora()}
        try:
            meta = generar_imagen(f["prompt"], int(f["semilla"]), destino)
            intento.update(estado="ok", error="", **meta)
            print(f"  ✓ {f['id_imagen']}  ({meta['segundos']:.0f}s)")
        except Exception as e:
            intento.update(estado="fallida", segundos="", error=str(e))
            print(f"  ✗ {f['id_imagen']}: {e}")
        # R7: cada intento se agrega al registro, también los fallidos
        previas = pd.concat([previas, pd.DataFrame([intento])], ignore_index=True)
        previas.to_csv(ruta_reg, index=False, encoding="utf-8-sig")
    print("  → imagenes/  ·  registro/generaciones.csv")


def _generadas_ok() -> pd.DataFrame:
    ruta = REG / "generaciones.csv"
    if not ruta.exists():
        sys.exit("Todavía no hay imágenes. Corre primero la etapa `generar`.")
    g = pd.read_csv(ruta, encoding="utf-8-sig")
    g = g[g["estado"] == "ok"].drop_duplicates("id_imagen", keep="last")
    existe = g["archivo"].map(lambda a: (RAIZ / str(a)).exists())
    if (~existe).any():
        print(f"  ⚠ {(~existe).sum()} imágenes del registro no están en imagenes/ y se omiten:"
              f" {', '.join(g.loc[~existe, 'id_imagen'].head(5))}{' ...' if (~existe).sum() > 5 else ''}")
        print("    Para volver a generarlas: python pipeline.py --etapa generar")
    return g[existe]


def etapa_contrastar(args):
    from agentes.contraste import contrastar
    print(f"[A3] Contraste visual  (modelo: {CONFIG['modelo_vision']})")
    p = cargar_protocolo()
    ruta = REG / "a3_contraste.csv"
    previas = pd.read_csv(ruta, encoding="utf-8-sig") if ruta.exists() else pd.DataFrame(columns=["id_imagen"])
    gen = _generadas_ok()
    gen = gen[~gen["id_imagen"].isin(set(previas["id_imagen"]))]
    if args.limite:
        gen = gen.head(args.limite)
    extras = []
    for _, f in gen.iterrows():
        t0 = time.time()
        r = contrastar(f.to_dict(), str(RAIZ / f["archivo"]), p)
        filas = pd.DataFrame(r["requisitos"]).assign(fecha=ahora())
        filas.to_csv(ruta, mode="a", header=not ruta.exists(), index=False)
        extras += [{"id_imagen": f["id_imagen"], "elemento": e} for e in r["elementos_no_solicitados"]]
        print(f"  · {f['id_imagen']}  ({time.time() - t0:.0f}s)")
    if extras:
        re = REG / "a3_elementos_no_solicitados.csv"
        pd.DataFrame(extras).to_csv(re, mode="a", header=not re.exists(), index=False)
    print("  → registro/a3_contraste.csv · registro/a3_elementos_no_solicitados.csv")
    print("    (A3 no dictamina autenticidad ni elimina imágenes)")


def etapa_codificar(_):
    from codificacion import preparar_hoja
    print("[H] Hoja de codificación para la investigadora")
    preparar_hoja(_generadas_ok())


def etapa_reporte(_):
    from reporte import generar_reporte
    generar_reporte()


ETAPAS = {"formular": etapa_formular, "prompts": etapa_prompts, "revisar": etapa_revisar,
          "generar": etapa_generar, "contrastar": etapa_contrastar, "codificar": etapa_codificar,
          "reporte": etapa_reporte}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", choices=list(ETAPAS))
    ap.add_argument("--limite", type=int, default=0, help="máximo de imágenes en generar / contrastar")
    a = ap.parse_args()
    for nombre, fn in ETAPAS.items():
        if a.etapa in (None, nombre):
            fn(a)
