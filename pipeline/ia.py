"""Etapa 3 — Cliente de IA generativa (Google Gemini).

Se usa la API REST de Gemini (Google AI Studio) con `requests`, sin SDK adicional.
La clave se lee de la variable de entorno GEMINI_API_KEY (archivo `.env` o secreto
de GitHub) y nunca se imprime ni se guarda.

Uso:
    python -m pipeline.ia --probar      # verifica la clave y el modelo disponible
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta"
# Orden de preferencia: modelos rápidos y con capa gratuita.
PREFERIDOS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.0-flash"]


class ErrorIA(RuntimeError):
    pass


def _clave() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    k = os.getenv("GEMINI_API_KEY", "").strip()
    if not k:
        raise ErrorIA("Falta GEMINI_API_KEY (en .env o como secreto del repositorio).")
    return k


def _explicar(r: requests.Response) -> str:
    try:
        err = r.json().get("error", {})
    except ValueError:
        err = {}
    estado, msg = err.get("status", ""), err.get("message", r.text[:200])
    razones = " ".join(d.get("reason", "") for d in err.get("details", []) if isinstance(d, dict))
    if "API_KEY_INVALID" in razones or "API key not valid" in msg:
        return "La clave GEMINI_API_KEY no es válida (revise que se copió completa, sin espacios)."
    if r.status_code == 403:
        return f"La clave no tiene permiso para la API de Gemini ({estado}): {msg}"
    if r.status_code == 429:
        return f"Se alcanzó el límite de uso de la capa gratuita ({estado}). Espere un momento y reintente."
    return f"HTTP {r.status_code} {estado}: {msg}"


def modelos(clave: str | None = None) -> list[str]:
    clave = clave or _clave()
    r = requests.get(f"{API}/models", headers={"x-goog-api-key": clave}, params={"pageSize": 200}, timeout=30)
    if r.status_code != 200:
        raise ErrorIA(_explicar(r))
    return [m["name"].split("/", 1)[1] for m in r.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]


def elegir_modelo(disponibles: list[str]) -> str:
    pedido = os.getenv("GEMINI_MODEL", "").strip()
    if pedido:
        if pedido not in disponibles:
            raise ErrorIA(f"El modelo {pedido} no está disponible para esta clave.")
        return pedido
    for m in PREFERIDOS:
        if m in disponibles:
            return m
    flash = [m for m in disponibles if "flash" in m]
    if not flash:
        raise ErrorIA("La clave no tiene acceso a ningún modelo Gemini Flash.")
    return sorted(flash)[-1]


def generar(prompt: str, *, modelo: str, clave: str | None = None, json_schema: dict | None = None,
            temperatura: float = 0.1, reintentos: int = 4) -> str:
    """Envía un prompt y devuelve el texto de la respuesta (JSON si se pasa json_schema)."""
    clave = clave or _clave()
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": temperatura}}
    if json_schema:
        cuerpo["generationConfig"].update(responseMimeType="application/json", responseSchema=json_schema)
    for intento in range(reintentos):
        r = requests.post(f"{API}/models/{modelo}:generateContent", headers={"x-goog-api-key": clave},
                          json=cuerpo, timeout=120)
        if r.status_code in (429, 500, 503) and intento < reintentos - 1:
            time.sleep(10 * (intento + 1))           # capa gratuita: respetar el límite por minuto
            continue
        if r.status_code != 200:
            raise ErrorIA(_explicar(r))
        cand = r.json().get("candidates") or [{}]
        partes = cand[0].get("content", {}).get("parts", [])
        texto = "".join(p.get("text", "") for p in partes)
        if not texto:
            raise ErrorIA(f"Respuesta vacía (finishReason={cand[0].get('finishReason')}).")
        return texto
    raise ErrorIA("Sin respuesta tras varios reintentos.")


def probar() -> dict:
    clave = _clave()
    t0 = time.time()
    disponibles = modelos(clave)
    modelo = elegir_modelo(disponibles)
    esquema = {"type": "OBJECT", "properties": {"estado": {"type": "STRING"}, "medicamento": {"type": "STRING"}},
               "required": ["estado", "medicamento"]}
    resp = generar('Devuelve estado="ok" y el principio activo de "GLIBENCLAMIDA, 5MG, TABLETA, V.O".',
                   modelo=modelo, clave=clave, json_schema=esquema)
    return {"clave": "válida", "modelo": modelo, "modelos_flash_disponibles": [m for m in disponibles if "flash" in m][:8],
            "respuesta": json.loads(resp), "segundos": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser(description="Cliente de IA generativa (Gemini)")
    ap.add_argument("--probar", action="store_true", help="verifica la clave y el modelo")
    a = ap.parse_args()
    if a.probar:
        try:
            print(json.dumps(probar(), ensure_ascii=False, indent=2))
        except ErrorIA as e:
            sys.exit(f"ERROR: {e}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
