"""Generación de imágenes. SIN modelo de lenguaje.

Tres vías, que se eligen en config.yaml → generador.via:
  local         Z-Image Turbo en la propia Mac, con mflux (plan A).
  pollinations  Z-Image Turbo por internet, gratis con clave de pollinations.ai (plan B).
  fal           Z-Image Turbo por internet en fal.ai, de pago (≈ 0.003 USD por imagen) (plan C).

Las tres usan el MISMO modelo, para que el cambio de vía no cambie el objeto de estudio.
En las vías por internet se DESACTIVA la "mejora automática del prompt": si el servicio
reescribiera el prompt, se romperían R1 y R2.
"""
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

import yaml

from llm import CONFIG, RAIZ, SIMULAR


def _clave(nombre: str) -> str:
    ruta = RAIZ / "claves.yaml"
    if not ruta.exists():
        raise RuntimeError("Falta claves.yaml. Copia claves_ejemplo.yaml como claves.yaml y pega tu clave.")
    clave = (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}).get(nombre, "")
    if not clave or "PEGA" in clave:
        raise RuntimeError(f"Falta la clave `{nombre}` en claves.yaml.")
    return clave.strip()


def describir_via() -> str:
    g = CONFIG["generador"]
    return "SIMULADA" if SIMULAR else {"local": "Z-Image Turbo · local (mflux)",
                                       "pollinations": "Z-Image Turbo · pollinations.ai",
                                       "fal": "Z-Image Turbo · fal.ai"}[g["via"]]


def generar_imagen(prompt: str, semilla: int, destino: Path) -> dict:
    """Genera una imagen en `destino`. Devuelve metadatos para el registro."""
    t0 = time.time()
    g = CONFIG["generador"]
    if SIMULAR:
        _imagen_simulada(prompt, semilla, destino)
        extra = {}
    elif g["via"] == "local":
        _local(prompt, semilla, destino)
        extra = {}
    elif g["via"] == "pollinations":
        extra = _pollinations(prompt, semilla, destino)
    elif g["via"] == "fal":
        extra = _fal(prompt, semilla, destino)
    else:
        raise RuntimeError(f"Vía desconocida en config.yaml: {g['via']}")
    return {"via": describir_via(), "segundos": round(time.time() - t0, 1), **extra}


# ---------------- Plan A · local (mflux) ----------------
def _comando(prompt, semilla, salida):
    g = CONFIG["generador"]
    cmd = [g["comando_local"], "--prompt", prompt, "--seed", str(semilla), "--steps", str(g["pasos"]),
           "--width", str(g["ancho"]), "--height", str(g["alto"]), "-q", str(g["cuantizacion"])]
    return cmd + (["--output", str(salida)] if salida is not None else [])


def _local(prompt, semilla, destino):
    g = CONFIG["generador"]
    if shutil.which(g["comando_local"]) is None:
        raise RuntimeError(f"No se encontró `{g['comando_local']}`. ¿Está instalado mflux? "
                           "Si no se puede instalar, cambia generador.via a 'pollinations' en config.yaml.")
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(_comando(prompt, semilla, destino), cwd=tmp, capture_output=True, text=True,
                           timeout=g["segundos_maximos"])
        if r.returncode != 0 and "unrecognized arguments" in r.stderr and "--output" in r.stderr:
            r = subprocess.run(_comando(prompt, semilla, None), cwd=tmp, capture_output=True, text=True,
                               timeout=g["segundos_maximos"])
            pngs = sorted(Path(tmp).glob("*.png"), key=lambda p: p.stat().st_mtime)
            if r.returncode == 0 and pngs:
                shutil.move(str(pngs[-1]), destino)
        if r.returncode != 0 or not destino.exists():
            raise RuntimeError((r.stderr or r.stdout or "sin mensaje").strip().splitlines()[-1])


# ---------------- Plan B · pollinations.ai ----------------
def _pollinations(prompt, semilla, destino):
    import requests
    g = CONFIG["generador"]
    url = f"https://gen.pollinations.ai/image/{quote(prompt, safe='')}"
    params = {"model": "zimage", "width": g["ancho"], "height": g["alto"], "seed": semilla,
              "enhance": "false", "nologo": "true", "private": "true"}
    for intento in range(3):
        r = requests.get(url, params=params, headers={"Authorization": f"Bearer {_clave('pollinations')}"},
                         timeout=g["segundos_maximos"])
        if r.status_code == 429:                      # demasiadas solicitudes: esperar y reintentar
            time.sleep(20 * (intento + 1))
            continue
        break
    if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image"):
        raise RuntimeError(f"pollinations respondió {r.status_code}: {r.text[:200]}")
    destino.write_bytes(r.content)
    time.sleep(g.get("pausa_segundos", 5))           # cortesía con el servicio gratuito
    return {}


# ---------------- Plan C · fal.ai ----------------
def _fal(prompt, semilla, destino):
    import requests
    g = CONFIG["generador"]
    r = requests.post("https://fal.run/fal-ai/z-image/turbo",
                      headers={"Authorization": f"Key {_clave('fal')}"},
                      json={"prompt": prompt, "seed": semilla, "num_images": 1, "output_format": "png",
                            "image_size": {"width": g["ancho"], "height": g["alto"]},
                            "num_inference_steps": min(g["pasos"], 8),
                            "enable_prompt_expansion": False},
                      timeout=g["segundos_maximos"])
    if r.status_code != 200:
        raise RuntimeError(f"fal respondió {r.status_code}: {r.text[:200]}")
    datos = r.json()
    imagen = requests.get(datos["images"][0]["url"], timeout=120)
    imagen.raise_for_status()
    destino.write_bytes(imagen.content)
    filtro = datos.get("has_nsfw_concepts") or [False]
    return {"filtro_contenido": bool(filtro[0])}   # se registra si el filtro del servicio intervino


# ---------------- Modo simulado ----------------
def _imagen_simulada(prompt, semilla, destino):
    from PIL import Image, ImageDraw
    import random
    random.seed(semilla + sum(map(ord, prompt)))
    img = Image.new("RGB", (512, 512), tuple(random.randint(60, 200) for _ in range(3)))
    d = ImageDraw.Draw(img)
    d.text((20, 20), "IMAGEN SIMULADA", fill="white")
    for i, linea in enumerate([prompt[k:k + 60] for k in range(0, len(prompt), 60)]):
        d.text((20, 60 + 18 * i), linea, fill="white")
    d.text((20, 480), f"semilla {semilla}", fill="white")
    img.save(destino)
