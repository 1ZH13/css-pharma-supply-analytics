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
            temperatura: float = 0.1, reintentos: int = 4, timeout: float = 90) -> str:
    """Envía un prompt y devuelve el texto de la respuesta (JSON si se pasa json_schema)."""
    clave = clave or _clave()
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": temperatura}}
    if json_schema:
        cuerpo["generationConfig"].update(responseMimeType="application/json", responseSchema=json_schema)
    for intento in range(reintentos):
        try:
            r = requests.post(f"{API}/models/{modelo}:generateContent", headers={"x-goog-api-key": clave},
                              json=cuerpo, timeout=(15, timeout))
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


LENTO = 45.0


class ClienteGemini:
    """Cliente con selección automática de modelo: si uno está retirado (404) o saturado
    (503), pasa al siguiente candidato y lo recuerda para las llamadas siguientes."""

    def __init__(self, pausa: float = 6.0, timeout: float = 90, reintentos: int = 3, max_modelos: int | None = None):
        """`timeout`, `reintentos` y `max_modelos` acotan la espera: el asistente del dashboard
        usa valores bajos para responder en segundos o avisar, en vez de esperar minutos."""
        self.clave = _clave()
        self.cands = candidatos(modelos(self.clave))[:max_modelos]
        self.timeout = timeout
        self.reintentos = reintentos
        self.i = 0
        self.pausa = pausa            # capa gratuita: ~10 solicitudes por minuto
        self.llamadas = 0
        self._ultima = 0.0
        self._lentas = 0             # respuestas de más de LENTO segundos con el modelo actual

    @property
    def modelo(self) -> str:
        return self.cands[min(self.i, len(self.cands) - 1)]

    def json(self, prompt: str, esquema: dict) -> dict:
        try:
            return json.loads(self._llamar(prompt, esquema))
        except json.JSONDecodeError as e:
            raise ErrorIA(f"Gemini devolvió JSON inválido: {e}") from e

    def texto(self, prompt: str, temperatura: float = 0.2) -> str:
        """Respuesta en texto libre (la usa el asistente del dashboard)."""
        return self._llamar(prompt, None, temperatura)

    def _llamar(self, prompt: str, esquema: dict | None, temperatura: float = 0.1) -> str:
        espera = self.pausa - (time.time() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        while self.i < len(self.cands):
            try:
                t0 = time.time()
                texto = generar(prompt, modelo=self.modelo, clave=self.clave, json_schema=esquema,
                                temperatura=temperatura, reintentos=self.reintentos, timeout=self.timeout)
                self._ultima = time.time()
                self.llamadas += 1
                if self._ultima - t0 > LENTO:
                    self._lentas += 1
                    if self._lentas >= 2 and self.i < len(self.cands) - 1:
                        self.i += 1              # modelo saturado: los siguientes pedidos van al próximo
                        self._lentas = 0
                return texto
            except ErrorIA as e:
                m = str(e)
                if any(k in m for k in ("404", "NOT_FOUND", "503", "UNAVAILABLE", "no está disponible")):
                    self.i += 1
                    self._lentas = 0
                    continue
                if "límite de uso" in m:
                    if self.reintentos > 1:          # pipeline: esperar a que se libere la cuota por minuto
                        time.sleep(60)
                        continue
                    self.i += 1                      # asistente: cada modelo tiene su propia cuota gratuita
                    self._lentas = 0
                    continue
                raise
        raise ErrorIA("Ningún modelo Gemini disponible respondió.")


# ---------------------------------------------------------------------------
# Proveedor alterno: cualquier API compatible con OpenAI (Groq por defecto).
# Lo usa el asistente del dashboard cuando la cuota gratuita de Gemini se agota.
ALTERNOS = {
    "GROQ_API_KEY": ("Groq", "https://api.groq.com/openai/v1"),
    "OPENROUTER_API_KEY": ("OpenRouter", "https://openrouter.ai/api/v1"),
}
# Orden de preferencia por nombre (el catálogo de modelos gratuitos cambia sin aviso,
# por eso se consulta /models y se elige el primero que coincida).
PREFERIDOS = ("llama-3.3-70b", "gpt-oss-120b", "llama-4-maverick", "llama-4-scout", "qwen3", "kimi-k2",
              "gpt-oss-20b", "llama-3.1-8b")
NO_TEXTO = ("whisper", "guard", "tts", "playai", "orpheus", "embed", "vision", "audio", "compound", "safeguard")


def candidatos_alternos(disponibles: list[str], pedido: str | None = None) -> list[str]:
    """Modelos de chat en orden de preferencia; `pedido` (variable ALT_MODEL) va primero."""
    chat = [m for m in disponibles if not any(x in m.lower() for x in NO_TEXTO)]
    orden = [m for p in PREFERIDOS for m in sorted(chat) if p in m.lower()]
    orden = ([pedido] if pedido else []) + orden + sorted(chat)
    return list(dict.fromkeys(orden))


class ClienteAlterno:
    """Cliente mínimo para APIs compatibles con OpenAI (chat/completions)."""

    def __init__(self, clave: str, nombre: str, base: str, timeout: float = 30, max_modelos: int = 3,
                 max_caracteres: int = 18000):
        self.clave, self.nombre, self.base, self.timeout = clave, nombre, base.rstrip("/"), timeout
        # La capa gratuita limita tokens por minuto: el contexto se recorta antes de enviarlo.
        self.max_caracteres = max_caracteres
        r = requests.get(f"{self.base}/models", headers=self._h(), timeout=20)
        if r.status_code != 200:
            raise ErrorIA(f"{nombre}: HTTP {r.status_code} al listar modelos")
        ids = [m.get("id", "") for m in r.json().get("data", [])]
        if nombre == "OpenRouter":
            ids = [m for m in ids if m.endswith(":free")]
        self.cands = candidatos_alternos(ids, os.getenv("ALT_MODEL", "").strip() or None)[:max_modelos]
        if not self.cands:
            raise ErrorIA(f"{nombre}: la clave no tiene modelos de chat disponibles.")
        self.i = 0

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.clave}"}

    @property
    def modelo(self) -> str:
        return f"{self.nombre} · {self.cands[min(self.i, len(self.cands) - 1)]}"

    def texto(self, prompt: str, temperatura: float = 0.2) -> str:
        if len(prompt) > self.max_caracteres:
            prompt = prompt[: self.max_caracteres - 400] + "\n[contexto recortado]\n" + prompt[-400:]
        while self.i < len(self.cands):
            modelo = self.cands[self.i]
            try:
                r = requests.post(f"{self.base}/chat/completions", headers=self._h(), timeout=(10, self.timeout),
                                  json={"model": modelo, "temperature": temperatura, "max_tokens": 700,
                                        "messages": [{"role": "user", "content": prompt}]})
            except (requests.Timeout, requests.ConnectionError):
                self.i += 1
                continue
            if r.status_code in (404, 413, 429, 500, 502, 503):
                self.i += 1                  # siguiente modelo (cada uno tiene su propia cuota)
                continue
            if r.status_code != 200:
                raise ErrorIA(f"{self.nombre}: HTTP {r.status_code} {r.text[:150]}")
            msg = (r.json().get("choices") or [{}])[0].get("message", {})
            texto = (msg.get("content") or "").strip()
            texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()   # modelos de razonamiento
            if texto:
                return texto
            self.i += 1
        raise ErrorIA(f"Ningún modelo de {self.nombre} respondió.")


class ClienteConRespaldo:
    """Intenta con Gemini; si falla (cuota, saturación, sin clave), pasa a los proveedores alternos."""

    def __init__(self, clientes: list):
        if not clientes:
            raise ErrorIA("No hay ningún proveedor de IA configurado (GEMINI_API_KEY o GROQ_API_KEY).")
        self.clientes = clientes
        self.actual = clientes[0]

    @property
    def modelo(self) -> str:
        m = self.actual.modelo
        return m if "·" in m else f"Gemini · {m}"

    def texto(self, prompt: str, temperatura: float = 0.2) -> str:
        errores = []
        for c in self.clientes:
            try:
                self.actual = c
                return c.texto(prompt, temperatura)
            except ErrorIA as e:
                errores.append(str(e)[:120])
        raise ErrorIA(" | ".join(errores))


def cliente_asistente(claves: dict, timeout: float = 30) -> ClienteConRespaldo:
    """Arma la cadena Gemini → Groq → OpenRouter con las claves que existan."""
    clientes, errores = [], []
    if claves.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = claves["GEMINI_API_KEY"]
        try:
            clientes.append(ClienteGemini(pausa=0, timeout=timeout, reintentos=1, max_modelos=4))
        except ErrorIA as e:
            errores.append(f"Gemini: {e}")
    for var, (nombre, base) in ALTERNOS.items():
        if claves.get(var):
            try:
                clientes.append(ClienteAlterno(claves[var], nombre, base, timeout=timeout))
            except (ErrorIA, requests.RequestException) as e:
                errores.append(f"{nombre}: {e}")
    if not clientes:
        raise ErrorIA("; ".join(errores) or "No hay claves de IA configuradas.")
    return ClienteConRespaldo(clientes)


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
