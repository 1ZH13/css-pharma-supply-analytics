"""CSS Pharma Supply Analytics — dashboard de la demo.

Ejecutar:  streamlit run dashboard/streamlit/app.py
Secretos (opcionales, en .streamlit/secrets.toml o en Streamlit Community Cloud):
    MONGODB_URI = "mongodb+srv://..."     # sin él, lee las tablas publicadas en GitHub
    GEMINI_API_KEY = "..."                # para el asistente
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asistente  # noqa: E402
import vistas  # noqa: E402

st.set_page_config(page_title="CSS · Inventario de medicamentos", page_icon="💊", layout="wide")
st.markdown("""<style>
  h1 {font-size: 2.0rem !important; line-height: 1.2; color: #3D1D5C;}
  [data-testid="stMetricValue"] {color: #5B2C83;}
  .block-container {padding-top: 2rem; max-width: 1250px;}
</style>""", unsafe_allow_html=True)

paginas = {
    "Resumen": [st.Page(vistas.inicio, title="Inicio", icon="🏥", default=True)],
    "Las 6 preguntas": [
        st.Page(vistas.p1, title="1 · El inventario en 2025", icon="📉", url_path="p1-inventario"),
        st.Page(vistas.p2, title="2 · ¿90 % de abastecimiento?", icon="📰", url_path="p2-abastecimiento"),
        st.Page(vistas.p3, title="3 · Quiénes pagan", icon="🧑‍⚕️", url_path="p3-pacientes"),
        st.Page(vistas.p4, title="4 · El interior", icon="🚚", url_path="p4-redistribucion"),
        st.Page(vistas.p5, title="5 · La Comisión", icon="🏛️", url_path="p5-comision"),
        st.Page(vistas.p6, title="6 · Medicamentos fantasma", icon="👻", url_path="p6-fantasmas"),
    ],
    "IA generativa": [st.Page(asistente.pagina, title="Pregúntale a los datos", icon="✨", url_path="asistente")],
}
st.navigation(paginas).run()
st.sidebar.caption("Proyecto final · Sistemas de Información Gerencial · UTP 2026")
st.sidebar.caption("[Código en GitHub](https://github.com/1ZH13/css-pharma-supply-analytics)")
