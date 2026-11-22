"""Etapa 3 — IA generativa sobre texto no estructurado.

1. **Análisis de noticias e informes** (`documentos.jsonl`): Gemini extrae con un esquema
   JSON fijo el tipo de evento, las causas del desabastecimiento, los medicamentos
   mencionados y su situación, los grupos de pacientes afectados, cifras, tono y riesgo.
2. **Cruce con el inventario**: cada medicamento mencionado se enlaza con los códigos CSS
   del catálogo (`medicamentos.csv`) por principio activo.
3. **Cruce con openFDA**: Gemini traduce los principios activos del catálogo al nombre
   internacional en inglés (INN/USAN, p. ej. GLIBENCLAMIDA → glyburide) para saber qué
   medicamentos de la CSS también están en escasez en EE. UU.

Las respuestas se guardan en `ia_cache.json` (clave = hash del texto + versión del prompt),
así cada ejecución solo envía a Gemini lo nuevo.

Salidas en data/processed/: ia_documentos.jsonl, ia_menciones.csv, ia_causas.csv,
inn_equivalencias.csv, cruce_fda.csv

Uso:  python -m pipeline.ia_texto  [--datos RUTA] [--cache RUTA] [--max-docs N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
from pathlib import Path

import pandas as pd

from .config import PROCESSED
from .ia import ClienteGemini, ErrorIA
from .lectura import sin_acentos

log = logging.getLogger("ia_texto")
VERSION_PROMPT = "v1"
MAX_CARACTERES = 60000          # los informes largos se recortan (cabecera + cuerpo principal)

TIPOS = ["desabastecimiento", "compra_o_licitacion", "mejora_abastecimiento", "robo_o_perdida",
         "queja_pacientes", "politica_o_regulacion", "informe_tecnico", "otro"]
CAUSAS = ["incumplimiento_proveedor", "proceso_de_compra", "presupuesto_o_pagos", "robo_o_perdida",
          "vencimiento", "logistica_distribucion", "demanda_creciente", "escasez_global",
          "gestion_institucional", "otra"]
SITUACION = ["faltante", "abastecido", "en_compra", "mencionado"]

ESQUEMA_DOC = {
    "type": "OBJECT",
    "properties": {
        "resumen": {"type": "STRING", "description": "2 o 3 oraciones en español"},
        "fecha_evento": {"type": "STRING", "description": "AAAA-MM-DD, AAAA-MM o AAAA; vacío si no se sabe"},
        "tipo_evento": {"type": "STRING", "enum": TIPOS},
        "causas": {"type": "ARRAY", "items": {"type": "STRING", "enum": CAUSAS}},
        "medicamentos": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "nombre": {"type": "STRING", "description": "como aparece en el texto"},
            "principio_activo": {"type": "STRING", "description": "en español, MAYÚSCULAS, sin dosis ni forma"},
            "situacion": {"type": "STRING", "enum": SITUACION}},
            "required": ["nombre", "principio_activo", "situacion"]}},
        "grupos_afectados": {"type": "ARRAY", "items": {"type": "STRING"}},
        "instalaciones": {"type": "ARRAY", "items": {"type": "STRING"}},
        "cifras": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "indicador": {"type": "STRING"}, "valor": {"type": "NUMBER"}, "unidad": {"type": "STRING"}},
            "required": ["indicador", "valor"]}},
        "nivel_abastecimiento_pct": {"type": "NUMBER", "nullable": True},
        "medidas_anunciadas": {"type": "ARRAY", "items": {"type": "STRING"}},
        "tono": {"type": "STRING", "enum": ["negativo", "neutro", "positivo"]},
        "riesgo": {"type": "STRING", "enum": ["alto", "medio", "bajo"],
                   "description": "riesgo de desabastecimiento que describe el texto"},
    },
    "required": ["resumen", "tipo_evento", "causas", "medicamentos", "grupos_afectados", "tono", "riesgo"],
}

PROMPT_DOC = """Eres analista de la cadena de suministro de medicamentos de la Caja de Seguro Social (CSS) de Panamá.
Lee el documento y extrae SOLO lo que el texto dice (no inventes ni completes con conocimiento externo).

- tipo_evento: el hecho principal del documento.
- causas: causas del desabastecimiento que el texto menciona o atribuye (vacío si no hay).
- medicamentos: cada medicamento o grupo concreto mencionado (p. ej. "insulina", "amlodipina"),
  con su principio activo en español y su situación según el texto.
- grupos_afectados: tipos de pacientes (p. ej. diabéticos, oncológicos, VIH, hipertensos, salud mental).
- instalaciones: hospitales, policlínicas, regiones o centros de distribución nombrados.
- cifras: porcentajes de abastecimiento, montos (B/. o USD), número de renglones o de pacientes.
- nivel_abastecimiento_pct: solo si el texto da un porcentaje de abastecimiento de la CSS.
- riesgo: alto si describe faltantes actuales que afectan pacientes; medio si hay amenazas o retrasos;
  bajo si describe normalidad o mejoras.

Metadatos: fuente={fuente}; fecha publicada={fecha}; título={titulo}

DOCUMENTO:
{texto}
"""

ESQUEMA_INN = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "es": {"type": "STRING"}, "inn_en": {"type": "STRING", "description": "nombre genérico en inglés (INN/USAN), minúsculas; vacío si no es un fármaco"}},
    "required": ["es", "inn_en"]}}
PROMPT_INN = """Traduce cada principio activo (español, como lo escribe la CSS de Panamá) a su nombre genérico
en inglés usado por la FDA de EE. UU. (USAN; si no existe, el INN). Ejemplos: GLIBENCLAMIDA → glyburide,
PARACETAMOL → acetaminophen, SALBUTAMOL → albuterol, ACIDO VALPROICO → valproic acid.
Quita sales solo si el nombre en inglés no la usa. Devuelve un elemento por cada entrada, en el mismo orden.

{lista}
"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", sin_acentos(str(s or "")).upper()).strip(" .,-")


def _hash(*partes: str) -> str:
    return hashlib.sha256("\x1f".join(partes).encode("utf-8")).hexdigest()[:24]


class Cache:
    def __init__(self, ruta: Path):
        self.ruta = ruta
        self.datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
        self.cambios = 0

    def get(self, k):
        return self.datos.get(k)

    def put(self, k, v):
        self.datos[k] = v
        self.cambios += 1
        if self.cambios % 5 == 0:
            self.guardar()

    def guardar(self):
        self.ruta.write_text(json.dumps(self.datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _cliente(estado: dict) -> ClienteGemini | None:
    """Cliente de Gemini, o None si no hay clave o se agotó el presupuesto de tiempo."""
    limite = estado.get("limite")
    if limite and time.time() > limite:
        if not estado.get("aviso_tiempo"):
            log.warning("Presupuesto de tiempo agotado: lo pendiente se procesa en la próxima ejecución.")
            estado["aviso_tiempo"] = True
        return None
    if estado.get("cliente") is None and not estado.get("sin_cliente"):
        try:
            estado["cliente"] = ClienteGemini()
        except ErrorIA as e:
            log.warning("Gemini no disponible: %s — se usa solo la caché.", e)
            estado["sin_cliente"] = True
    return estado.get("cliente")


# ------------------------------------------------------------- documentos
def analizar_documentos(datos: Path, cache: Cache, estado: dict, max_docs: int | None = None) -> list[dict]:
    docs = [json.loads(l) for l in (datos / "documentos.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    salida, nuevos = [], 0
    for d in docs:
        texto = d.get("texto") or ""
        if len(texto) < 300:
            continue
        texto = texto[:MAX_CARACTERES]
        k = _hash(VERSION_PROMPT, "doc", texto)
        r = cache.get(k)
        if r is None:
            if max_docs is not None and nuevos >= max_docs:
                continue
            cli = _cliente(estado)
            if cli is None:
                continue
            prompt = PROMPT_DOC.format(fuente=d.get("fuente", ""), fecha=d.get("fecha", ""),
                                       titulo=d.get("titulo", ""), texto=texto)
            try:
                r = cli.json(prompt, ESQUEMA_DOC)
            except ErrorIA as e:
                log.warning("%s: %s", d.get("id"), e)
                continue
            r["_modelo"] = cli.modelo
            cache.put(k, r)
            cache.guardar()
            nuevos += 1
            log.info("Analizado %s con %s", d.get("id"), cli.modelo)
        salida.append({"id": d.get("id"), "tipo_documento": d.get("tipo"), "fuente": d.get("fuente"),
                       "fecha_publicada": d.get("fecha"), "titulo": d.get("titulo"), "url": d.get("url"),
                       "modelo": r.get("_modelo"), **{k2: v for k2, v in r.items() if not k2.startswith("_")}})
    return salida


def menciones(analisis: list[dict], catalogo: pd.DataFrame) -> pd.DataFrame:
    """Una fila por medicamento mencionado × código CSS que le corresponde."""
    cat = catalogo.assign(pa=catalogo["principio_activo"].map(_norm), desc=catalogo["descripcion"].map(_norm))
    filas = []
    for a in analisis:
        for m in a.get("medicamentos") or []:
            pa = _norm(m.get("principio_activo") or m.get("nombre"))
            if not pa or pa in {"NO ESPECIFICADO", "NO ESPECIFICADA", "N/A", "NINGUNO", "VARIOS", "MEDICAMENTOS"}:
                continue
            exacto = cat[cat["pa"] == pa]
            parcial = cat[cat["pa"].str.startswith(pa + " ") | cat["desc"].str.contains(rf"\b{re.escape(pa)}\b", regex=True)]
            hallados = exacto if not exacto.empty else parcial
            base = {"documento": a["id"], "fuente": a.get("fuente"), "fecha_evento": a.get("fecha_evento") or a.get("fecha_publicada"),
                    "tipo_evento": a.get("tipo_evento"), "riesgo": a.get("riesgo"),
                    "mencion": m.get("nombre"), "principio_activo_mencion": pa, "situacion": m.get("situacion")}
            if hallados.empty:
                filas.append({**base, "codigo": None, "descripcion_css": None, "coincidencia": "sin_coincidencia"})
            for r in hallados.itertuples():
                filas.append({**base, "codigo": r.codigo, "descripcion_css": r.descripcion,
                              "coincidencia": "exacta" if not exacto.empty else "parcial"})
    return pd.DataFrame(filas)


def causas(analisis: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{"documento": a["id"], "fuente": a.get("fuente"),
                          "fecha_evento": a.get("fecha_evento") or a.get("fecha_publicada"),
                          "tipo_evento": a.get("tipo_evento"), "causa": c, "riesgo": a.get("riesgo")}
                         for a in analisis for c in (a.get("causas") or [])])


# ------------------------------------------------------------ openFDA
def equivalencias_inn(catalogo: pd.DataFrame, cache: Cache, estado: dict, lote: int = 120) -> pd.DataFrame:
    principios = sorted({_norm(p) for p in catalogo["principio_activo"].dropna() if _norm(p)})
    res, pendientes = {}, []
    for p in principios:
        v = cache.get(_hash(VERSION_PROMPT, "inn", p))
        if v is None:
            pendientes.append(p)
        else:
            res[p] = v
    for i in range(0, len(pendientes), lote):
        bloque = pendientes[i:i + lote]
        cli = _cliente(estado)
        if cli is None:
            break
        try:
            r = cli.json(PROMPT_INN.format(lista="\n".join(bloque)), ESQUEMA_INN)
        except ErrorIA as e:
            log.warning("Traducción INN: %s", e)
            continue
        por_es = {_norm(x.get("es")): (x.get("inn_en") or "").strip().lower() for x in r}
        for j, p in enumerate(bloque):
            inn = por_es.get(p, r[j].get("inn_en", "").strip().lower() if j < len(r) else "")
            cache.put(_hash(VERSION_PROMPT, "inn", p), inn)
            res[p] = inn
    return pd.DataFrame([{"principio_activo": p, "inn_en": res.get(p, "")} for p in principios])


def cruce_fda(catalogo: pd.DataFrame, inn: pd.DataFrame, fda: pd.DataFrame) -> pd.DataFrame:
    if fda.empty or inn.empty:
        return pd.DataFrame()
    f = fda.assign(nombre=(fda["sustancia"].fillna("") + " | " + fda["generic_name"].fillna("")).str.lower())
    mapa = dict(zip(inn["principio_activo"], inn["inn_en"]))
    filas = []
    for r in catalogo.itertuples():
        en = mapa.get(_norm(r.principio_activo), "")
        if not en or len(en) < 4:
            continue
        hits = f[f["nombre"].str.contains(rf"\b{re.escape(en)}\b", regex=True)]
        actuales = hits[hits["status"].str.lower() == "current"]
        filas.append({
            "codigo": r.codigo, "principio_activo": r.principio_activo, "inn_en": en,
            "registros_fda": len(hits), "registros_fda_vigentes": len(actuales),
            "escasez_eeuu_vigente": bool(len(actuales)),
            "motivos_fda": "; ".join(sorted({m for m in actuales.get("motivo", pd.Series(dtype=str)).dropna()}))[:300],
            "ultima_actualizacion_fda": hits["fecha_actualizacion"].max() if len(hits) else None,
        })
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ main
def ejecutar(datos: Path = PROCESSED, cache_ruta: Path | None = None, max_docs: int | None = None,
             presupuesto_min: float | None = None) -> dict:
    cache = Cache(cache_ruta or datos / "ia_cache.json")
    estado: dict = {"limite": time.time() + presupuesto_min * 60 if presupuesto_min else None}
    catalogo = pd.read_csv(datos / "medicamentos.csv", dtype={"codigo": str})
    fda = pd.read_csv(datos / "fda_escasez.csv") if (datos / "fda_escasez.csv").exists() else pd.DataFrame()

    analisis = analizar_documentos(datos, cache, estado, max_docs)
    inn = equivalencias_inn(catalogo, cache, estado)
    cache.guardar()

    opts = {"index": False, "encoding": "utf-8-sig"}
    with (datos / "ia_documentos.jsonl").open("w", encoding="utf-8") as fh:
        for a in analisis:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    men = menciones(analisis, catalogo)
    men.to_csv(datos / "ia_menciones.csv", **opts)
    causas(analisis).to_csv(datos / "ia_causas.csv", **opts)
    inn.to_csv(datos / "inn_equivalencias.csv", **opts)
    cfda = cruce_fda(catalogo, inn, fda)
    cfda.to_csv(datos / "cruce_fda.csv", **opts)

    cli = estado.get("cliente")
    total_docs = sum(1 for l in (datos / "documentos.jsonl").read_text(encoding="utf-8").splitlines()
                     if l.strip() and len(json.loads(l).get("texto") or "") >= 300)
    return {"documentos_analizados": len(analisis), "documentos_con_texto": total_docs,
            "pendientes": total_docs - len(analisis), "llamadas_gemini": cli.llamadas if cli else 0,
            "modelo": cli.modelo if cli else None, "menciones": len(men),
            "menciones_con_codigo_css": int(men["codigo"].notna().sum()) if len(men) else 0,
            "principios_traducidos": int((inn["inn_en"] != "").sum()) if len(inn) else 0,
            "medicamentos_css_en_escasez_eeuu": int(cfda["escasez_eeuu_vigente"].sum()) if len(cfda) else 0}


def main():
    ap = argparse.ArgumentParser(description="IA generativa sobre noticias e informes (Gemini)")
    ap.add_argument("--datos", type=Path, default=PROCESSED)
    ap.add_argument("--cache", type=Path, default=None, help="ruta de ia_cache.json (por defecto en --datos)")
    ap.add_argument("--max-docs", type=int, default=None, help="máximo de documentos nuevos a enviar a Gemini")
    ap.add_argument("--presupuesto-min", type=float, default=None,
                    help="minutos máximos de consultas a Gemini; lo pendiente queda para la próxima ejecución")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(ejecutar(a.datos, a.cache, a.max_docs, a.presupuesto_min), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
