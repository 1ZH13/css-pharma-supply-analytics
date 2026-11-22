"""IA generativa (uso 3): asistente "Pregúntale a los datos".

Gemini responde preguntas en lenguaje natural usando SOLO un contexto armado con las
tablas del sistema (cifras de las 6 preguntas, KPI y las filas relevantes según lo que se
pregunta). No tiene acceso a internet ni inventa cifras: si el dato no está, lo dice.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

import datos

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.ia import ClienteGemini, ErrorIA  # noqa: E402

SUGERENCIAS = [
    "¿Qué oncológicos están sin existencia y dónde hay para trasladar?",
    "¿Qué le falta hoy a Chiriquí que sí hay en Panamá?",
    "¿Por qué cayó tanto el inventario en 2025?",
    "Resume en 3 puntos qué decisiones debería tomar la CSS este mes.",
]
GRUPOS = {"onco": "Oncológicos", "cancer": "Oncológicos", "cáncer": "Oncológicos", "vih": "Antivirales (incluye VIH)",
          "antiretro": "Antivirales (incluye VIH)", "insulin": "Insulinas", "diabet": "Antidiabéticos orales",
          "asma": "Asma y EPOC", "epoc": "Asma y EPOC", "epilep": "Antiepilépticos", "corazon": "Cardiovascular",
          "cardio": "Cardiovascular", "hiperten": "Cardiovascular", "tiroid": "Tiroides", "inmuno": "Inmunosupresores",
          "anticoag": "Antitrombóticos", "hormonal": "Terapia hormonal oncológica"}
CENTROS = {"chiriqu": "CDCH", "david": "CDCH", "divisa": "CDDI", "azuero": "CDDI", "herrera": "CDDI", "cocl": "CDDI",
           "veragua": "CDDI", "panam": "CDPA", "cdpa": "CDPA", "cddi": "CDDI", "cdch": "CDCH"}
COLS = ["descripcion", "categoria_critica", "existencia_total", "existencia_CDPA", "existencia_CDDI", "existencia_CDCH",
        "cobertura_meses", "nivel_riesgo", "puntaje_riesgo", "escasez_eeuu", "motivos"]

PROMPT = """Eres el asistente del Sistema de Información Gerencial de inventario de medicamentos de la
Caja de Seguro Social (CSS) de Panamá. Respondes a gerentes en español, claro y breve (máximo 180 palabras,
usa viñetas si ayuda).

Reglas:
- Usa SOLO los datos del CONTEXTO. Si la respuesta no está ahí, dilo y sugiere qué página del dashboard revisar.
- Cita las cifras tal cual aparecen y el mes de corte. No inventes medicamentos, cantidades ni causas.
- Centros: CDPA = Panamá, CDDI = Divisa, CDCH = Chiriquí. "Cobertura" = meses de existencia al consumo estimado.
- Si hablas de causas, aclara que vienen de noticias analizadas con IA, no de los datos de inventario.

CONTEXTO
{contexto}

PREGUNTA: {pregunta}
"""


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _tabla(df: pd.DataFrame, n: int = 20) -> str:
    return df.head(n).to_csv(index=False) if len(df) else "(sin filas)"


def contexto(pregunta: str) -> str:
    q = _norm(pregunta)
    partes = [f"Cifras de las 6 preguntas: {json.dumps(datos.documento('preguntas_resumen'), ensure_ascii=False)}",
              f"KPI del último mes: {json.dumps(datos.documento('kpi_resumen'), ensure_ascii=False)}"]
    rg = datos.tabla("riesgo_medicamentos")
    rg = rg[[c for c in COLS if c in rg]]
    palabras = [w for w in re.findall(r"[a-z]{5,}", q)]
    if palabras:
        desc = rg["descripcion"].map(lambda s: _norm(str(s)))
        hit = rg[desc.apply(lambda d: any(w in d for w in palabras))]
        if 0 < len(hit) <= 40:
            partes.append("Medicamentos mencionados en la pregunta:\n" + _tabla(hit, 25))
    grupos = {g for k, g in GRUPOS.items() if k in q}
    for g in grupos:
        partes.append(f"Medicamentos del grupo {g} (ordenados por riesgo):\n" + _tabla(rg[rg["categoria_critica"] == g], 25))
    centros = {c for k, c in CENTROS.items() if k in q}
    red = datos.tabla("redistribucion")
    for c in centros:
        partes.append(f"Traslados sugeridos hacia {c}:\n" + _tabla(red[red["hacia"] == c][["descripcion", "desde", "hacia", "cantidad", "valor", "critico"]], 25))
        partes.append(f"Medicamentos sin existencia en {c} pero con existencia en otro centro:\n"
                      + _tabla(rg[(rg[f"existencia_{c}"] <= 0) & (rg["existencia_total"] > 0)][["descripcion", "categoria_critica", f"existencia_{c}", "existencia_total"]], 25))
    if not (grupos or centros):
        partes.append("Medicamentos críticos en riesgo alto:\n" + _tabla(rg[(rg["nivel_riesgo"] == "alto") & rg["categoria_critica"].notna()], 20))
    if any(k in q for k in ("por que", "causa", "noticia", "prensa", "anuncia", "declar")):
        ia = datos.jsonl("ia_documentos")
        partes.append("Noticias analizadas con IA: " + json.dumps(
            [{k: d.get(k) for k in ("fuente", "fecha_evento", "tipo_evento", "causas", "nivel_abastecimiento_pct", "resumen")} for d in ia],
            ensure_ascii=False))
    return "\n\n".join(partes)[:60000]


@st.cache_resource(show_spinner=False)
def _cliente():
    clave = datos.secreto("GEMINI_API_KEY")
    if not clave:
        return None
    os.environ["GEMINI_API_KEY"] = clave
    return ClienteGemini(pausa=0, timeout=30, reintentos=1, max_modelos=4)


def pagina():
    st.caption("IA generativa · Gemini responde solo con los datos del sistema")
    st.title("Pregúntale a los datos")
    try:
        cli = _cliente()
    except ErrorIA as e:
        cli = None
        st.error(f"No se pudo conectar con Gemini: {e}")
    if cli is None:
        st.warning("El asistente necesita la clave GEMINI_API_KEY en los secretos de Streamlit.")
        return
    if "chat" not in st.session_state:
        st.session_state.chat = []
    cols = st.columns(len(SUGERENCIAS))
    elegida = None
    for c, s in zip(cols, SUGERENCIAS):
        if c.button(s, width="stretch"):
            elegida = s
    for m in st.session_state.chat:
        st.chat_message(m["rol"]).markdown(m["texto"])
    pregunta = st.chat_input("Escribe tu pregunta sobre el inventario de medicamentos…") or elegida
    if not pregunta:
        return
    st.chat_message("user").markdown(pregunta)
    st.session_state.chat.append({"rol": "user", "texto": pregunta})
    with st.chat_message("assistant"):
        with st.spinner("Consultando los datos…"):
            try:
                ctx = contexto(pregunta)
                r = cli.texto(PROMPT.format(contexto=ctx, pregunta=pregunta))
            except ErrorIA as e:
                _cliente.clear()
                r = f"No pude consultar a Gemini en este momento ({e}). Intenta de nuevo en un minuto."
            except Exception as e:  # noqa: BLE001 - la demo no debe quedarse colgada
                r = f"No pude preparar la respuesta ({type(e).__name__}). Intenta de nuevo."
        st.markdown(r)
        st.caption(f"Modelo: {cli.modelo} · Datos: {datos.origen()}")
    st.session_state.chat.append({"rol": "assistant", "texto": r})
