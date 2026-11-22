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
import re
import sys
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta"
# Se prefiere el Gemini "Flash" estable más reciente (rápido y con capa gratuita).
# Google retira versiones para usuarios nuevos, por eso el modelo no se fija en el código.
RE_FLASH = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash$")


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


def candidatos(disponibles: list[str]) -> list[str]:
    """Modelos en orden de preferencia: GEMINI_MODEL, Flash estables por versión descendente, alias."""
    pedido = os.getenv("GEMINI_MODEL", "").strip()
    estables = sorted((m for m in disponibles if RE_FLASH.match(m)),
                      key=lambda m: float(RE_FLASH.match(m).group(1)), reverse=True)
    alias = [m for m in ("gemini-flash-latest",) if m in disponibles]
    otros = sorted((m for m in disponibles if "flash" in m and m not in estables + alias
                    and not any(x in m for x in ("image", "tts", "audio", "live", "embedding"))), reverse=True)
    orden = ([pedido] if pedido else []) + estables + alias + otros
    if not orden:
        raise ErrorIA("La clave no tiene acceso a ningún modelo Gemini Flash.")
    return list(dict.fromkeys(orden))


def generar(prompt: str, *, modelo: str, clave: str | None = None, json_schema: dict | None = None,
            temperatura: float = 0.1, reintentos: int = 4) -> str:
    """Envía un prompt y devuelve el texto de la respuesta (JSON si se pasa json_schema)."""
    clave = clave or _clave()
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": temperatura}}
    if json_schema:
        cuerpo["generationConfig"].update(responseMimeType="application/json", responseSchema=json_schema)
    for intento in range(reintentos):
        try:
            r = requests.post(f"{API}/models/{modelo}:generateContent", headers={"x-goog-api-key": clave},
                              json=cuerpo, timeout=(15, 90))
        except (requests.Timeout, requests.ConnectionError) as e:
            if intento < reintentos - 1:
                time.sleep(10 * (intento + 1))
                continue
            # Se trata como saturación (503) para que el cliente pruebe otro modelo
            raise ErrorIA(f"503 UNAVAILABLE: sin respuesta de {modelo} ({type(e).__name__})") from e
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
    esquema = {"type": "OBJECT", "properties": {"estado": {"type": "STRING"}, "medicamento": {"type": "STRING"}},
               "required": ["estado", "medicamento"]}
    descartados = {}
    for modelo in candidatos(disponibles)[:6]:
        try:
            resp = generar('Devuelve estado="ok" y el principio activo de "GLIBENCLAMIDA, 5MG, TABLETA, V.O".',
                           modelo=modelo, clave=clave, json_schema=esquema, reintentos=2)
        except ErrorIA as e:
            descartados[modelo] = str(e)[:120]
            continue
        return {"clave": "válida", "modelo": modelo, "respuesta": json.loads(resp),
                "segundos": round(time.time() - t0, 1), "descartados": descartados,
                "flash_disponibles": [m for m in disponibles if "flash" in m][:10]}
    raise ErrorIA(f"La clave es válida pero ningún modelo respondió: {descartados}")


def elegir_modelo(clave: str | None = None) -> str:
    """Primer modelo candidato que responde (lo usa la Etapa 3)."""
    return probar()["modelo"]


class ClienteGemini:
    """Cliente con selección automática de modelo: si uno está retirado (404) o saturado
    (503), pasa al siguiente candidato y lo recuerda para las llamadas siguientes."""

    def __init__(self, pausa: float = 6.0):
        self.clave = _clave()
        self.cands = candidatos(modelos(self.clave))
        self.i = 0
        self.pausa = pausa            # capa gratuita: ~10 solicitudes por minuto
        self.llamadas = 0
        self._ultima = 0.0

    @property
    def modelo(self) -> str:
        return self.cands[self.i]

    def json(self, prompt: str, esquema: dict) -> dict:
        espera = self.pausa - (time.time() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        while self.i < len(self.cands):
            try:
                texto = generar(prompt, modelo=self.modelo, clave=self.clave, json_schema=esquema, reintentos=3)
                self._ultima = time.time()
                self.llamadas += 1
                return json.loads(texto)
            except ErrorIA as e:
                m = str(e)
                if any(k in m for k in ("404", "NOT_FOUND", "503", "UNAVAILABLE", "no está disponible")):
                    self.i += 1
                    continue
                if "límite de uso" in m:
                    time.sleep(60)
                    continue
                raise
            except json.JSONDecodeError as e:
                raise ErrorIA(f"Gemini devolvió JSON inválido: {e}") from e
        raise ErrorIA("Ningún modelo Gemini disponible respondió.")


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
