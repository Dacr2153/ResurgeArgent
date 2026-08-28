#!/usr/bin/env python3
"""
Prueba la API key de Gemini y evalua que modelos sirven para ResurgeAgent.

Uso:
    python3 check_keys.py              # prueba los modelos candidatos
    python3 check_keys.py --list       # solo lista los modelos disponibles
    python3 check_keys.py --all        # prueba TODOS los modelos que soporten generacion

Lee GEMINI_API_KEY del entorno o de un archivo .env en este directorio.
Sin dependencias externas: solo stdlib.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 60
REINTENTOS = 3  # reintentos ante HTTP 503 (saturacion temporal)

# Modelos que nos interesan para el proyecto. Se filtran contra los que
# la key realmente tenga habilitados.
CANDIDATOS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
]

# --------------------------------------------------------------------------
# Pruebas reales contra lo que necesita el sistema:
#   1. Extraccion estructurada (Agente de Ingesta)  -> JSON schema
#   2. Clasificacion de severidad (Agente de Necesidades)
# --------------------------------------------------------------------------

REPORTE_CRUDO = (
    "buenas, aca en el barrio la esperanza calle 12 con 7 se cayo un muro y "
    "hay como 3 casas inundadas, hay una senora mayor que no puede salir y un "
    "nino con asma sin medicinas. no hay luz desde anoche. urgente porfa"
)

SCHEMA_REPORTE = {
    "type": "object",
    "properties": {
        "ubicacion": {"type": "string"},
        "severidad": {"type": "string", "enum": ["baja", "media", "alta", "critica"]},
        "personas_afectadas": {"type": "integer"},
        "necesidades": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "rescate",
                    "agua",
                    "alimentos",
                    "medicamentos",
                    "refugio",
                    "energia",
                    "transporte",
                ],
            },
        },
        "poblacion_vulnerable": {"type": "boolean"},
    },
    "required": [
        "ubicacion",
        "severidad",
        "personas_afectadas",
        "necesidades",
        "poblacion_vulnerable",
    ],
}


def cargar_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env = Path(__file__).parent / ".env"
    if env.exists():
        for linea in env.read_text().splitlines():
            linea = linea.strip()
            if linea.startswith("GEMINI_API_KEY="):
                return linea.split("=", 1)[1].strip().strip("\"'")
    sys.exit(
        "ERROR: falta GEMINI_API_KEY.\n"
        "  export GEMINI_API_KEY=...   o cree un .env con GEMINI_API_KEY=..."
    )


def pedir(url: str, payload: dict | None = None) -> tuple[int, dict]:
    datos = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=datos,
        headers={"Content-Type": "application/json"},
        method="POST" if datos else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(cuerpo)
        except json.JSONDecodeError:
            return e.code, {"error": {"message": cuerpo[:300]}}
    except Exception as e:  # timeout, DNS, etc.
        return 0, {"error": {"message": f"{type(e).__name__}: {e}"}}


def listar_modelos(key: str) -> list[dict]:
    modelos, token = [], ""
    while True:
        url = f"{BASE}/models?key={key}&pageSize=200"
        if token:
            url += f"&pageToken={token}"
        estado, cuerpo = pedir(url)
        if estado != 200:
            msg = cuerpo.get("error", {}).get("message", cuerpo)
            sys.exit(f"ERROR listando modelos (HTTP {estado}): {msg}")
        modelos += cuerpo.get("models", [])
        token = cuerpo.get("nextPageToken", "")
        if not token:
            return modelos


def probar(key: str, modelo: str) -> dict:
    """Corre la extraccion estructurada y devuelve metricas."""
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "Extrae la informacion de este reporte ciudadano "
                        f"de emergencia:\n\n{REPORTE_CRUDO}"
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA_REPORTE,
            "temperature": 0,
        },
    }
    url = f"{BASE}/models/{modelo}:generateContent?key={key}"
    # 503 = saturacion temporal del modelo, no un fallo real. Reintentamos.
    intentos = 0
    for intentos in range(1, REINTENTOS + 1):
        t0 = time.perf_counter()
        estado, cuerpo = pedir(url, payload)
        ms = int((time.perf_counter() - t0) * 1000)
        if estado != 503 or intentos == REINTENTOS:
            break
        time.sleep(2 * intentos)

    if estado != 200:
        return {
            "ok": False,
            "ms": ms,
            "error": f"HTTP {estado}: {cuerpo.get('error', {}).get('message', '')[:90]}",
            "intentos": intentos,
        }

    try:
        texto = cuerpo["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(texto)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return {"ok": False, "ms": ms, "error": f"respuesta no parseable ({e})"}

    faltan = [c for c in SCHEMA_REPORTE["required"] if c not in parsed]
    uso = cuerpo.get("usageMetadata", {})
    return {
        "ok": not faltan,
        "ms": ms,
        "tokens_in": uso.get("promptTokenCount", 0),
        "tokens_out": uso.get("candidatesTokenCount", 0),
        "error": f"faltan campos: {faltan}" if faltan else "",
        "intentos": intentos,
        "salida": parsed,
    }


def main() -> int:
    key = cargar_key()
    print(f"Key cargada: ...{key[-6:]}  ({len(key)} chars)\n")

    modelos = listar_modelos(key)
    generativos = {
        m["name"].removeprefix("models/")
        for m in modelos
        if "generateContent" in m.get("supportedGenerationMethods", [])
    }
    print(f"Modelos visibles: {len(modelos)}  |  con generateContent: {len(generativos)}")

    if "--list" in sys.argv:
        for n in sorted(generativos):
            print("  ", n)
        return 0

    if "--all" in sys.argv:
        objetivo = sorted(generativos)
    else:
        objetivo = [m for m in CANDIDATOS if m in generativos]
        ausentes = [m for m in CANDIDATOS if m not in generativos]
        if ausentes:
            print(f"No disponibles con esta key: {', '.join(ausentes)}")

    if not objetivo:
        print("\nNinguno de los modelos candidatos esta disponible. Use --list.")
        return 1

    print(f"\nProbando {len(objetivo)} modelo(s) con extraccion estructurada JSON:\n")
    print(f"{'MODELO':<34} {'OK':<4} {'ms':>7} {'tok_in':>7} {'tok_out':>8} {'try':>3}  NOTA")
    print("-" * 88)

    resultados = []
    for m in objetivo:
        r = probar(key, m)
        resultados.append((m, r))
        marca = "si" if r["ok"] else "NO"
        print(
            f"{m:<34} {marca:<4} {r['ms']:>7} "
            f"{r.get('tokens_in', 0):>7} {r.get('tokens_out', 0):>8} "
            f"{r.get('intentos', 1):>3}  {r['error']}"
        )

    buenos = [(m, r) for m, r in resultados if r["ok"]]
    print()
    if not buenos:
        print("Ningun modelo paso la prueba. Revise la key o la facturacion.")
        return 1

    ejemplo = buenos[0]
    print(f"Ejemplo de salida ({ejemplo[0]}):")
    print(json.dumps(ejemplo[1]["salida"], indent=2, ensure_ascii=False))

    rapido = min(buenos, key=lambda x: x[1]["ms"])
    print(f"\nMas rapido que funciona: {rapido[0]} ({rapido[1]['ms']} ms)")
    print(f"Modelos utilizables: {len(buenos)}/{len(resultados)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
