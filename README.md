# Representaciones IA

> **English summary.** A team of assistant agents for studying how generative image models represent Mexican women. A collaborative project of the MA in Digital Communication and Humanities, Universidad del Claustro de Sor Juana (Mexico City).
>
> **How it works**
> 1. One agent helps formulate the research question from a written protocol.
> 2. Prompts are built by plain code (no model), and a second agent reviews them.
> 3. Nothing is generated until a human approval is recorded in the protocol.
> 4. Images are generated locally (Z-Image Turbo via mflux), and every attempt is logged; none is deleted.
> 5. A vision agent (qwen3-vl) produces a visual contrast, researchers code the images by hand in Excel, and Cohen's kappa measures agreement.
>
> **Design principles:** agents propose, review and contrast; the researcher decides, describes and interprets. Whatever can be done without a model is done without one. Everything runs locally by default, and any use of an online route is recorded on each image.
>
> The documentation below is in Spanish.

---


Equipo de agentes auxiliares para estudiar representaciones de mujeres mexicanas en imágenes generativas.
Proyecto colaborativo de la Maestría en Comunicación y Humanidades Digitales · Universidad del Claustro de Sor Juana.

```
protocolo.yaml ─▶ [A1] formula/pregunta ─▶ prompts.py (sin modelo) ─▶ [A2] revisa
      │                                                                   │
      └──── aprobación humana (R6) ◀──────────────────────────────────────┘
                     │
                     ▼
     generador local (Z-Image Turbo · mflux) ─▶ registro/generaciones.csv (R7)
                     │
                     ▼
     [A3] contraste visual (qwen3-vl) ─▶ codificación humana en Excel (R8) ─▶ reporte ─▶ kappa
```

## Arranque rápido
```bash
ollama pull qwen3:14b && ollama pull qwen3-vl:8b
curl -LsSf https://astral.sh/uv/install.sh | sh     # luego abrir una terminal nueva
uv tool install --upgrade mflux

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

REPRESENTACIONES_SIMULAR=1 python pipeline.py --etapa prompts   # prueba sin modelos
python pipeline.py --etapa formular                             # A1
python pipeline.py --etapa prompts && python pipeline.py --etapa revisar   # A2
# aprobar en protocolo.yaml, luego:
python pipeline.py --etapa generar --limite 4
```

Si mflux no puede instalarse: copiar `claves_ejemplo.yaml` como `claves.yaml`, pegar la clave de pollinations.ai
y cambiar `via` a `"pollinations"` en `config.yaml` (mismo modelo, por internet, gratis).

La guía paso a paso está en **GUIA_SESION.html** (doble clic para abrirla en el navegador).

## Principios
- Los agentes proponen, revisan y contrastan; la investigadora decide, describe e interpreta.
- Lo que puede hacerse sin modelo se hace sin modelo (sustitución de términos, conteos, requisitos no verificables).
- Nada se genera sin aprobación registrada; ningún intento se borra.
- Por defecto todo corre en local; si se usa una vía por internet, queda registrada en cada imagen.
