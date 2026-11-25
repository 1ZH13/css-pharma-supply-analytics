"""CSS Pharma Supply Analytics — dashboard de la demo.

Ejecutar:  streamlit run dashboard/streamlit/app.py
Secretos (opcionales, en .streamlit/secrets.toml o en Streamlit Community Cloud):
    MONGODB_URI = "mongodb+srv://..."     # sin él, lee las tablas publicadas en GitHub
    GEMINI_API_KEY = "..."                # asistente (proveedor principal)
    GROQ_API_KEY = "..."                  # asistente (respaldo si se agota la cuota de Gemini)
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asistente  # noqa: E402
import vistas  # noqa: E402

st.set_page_config(page_title="CSS · Inventario de medicamentos", page_icon=":material/medication:", layout="wide")
st.markdown("""<style>
  h1 {font-size: 2.0rem !important; line-height: 1.2; color: #0A2F5C;}
  h2, h3 {color: #0B5394;}
  [data-testid="stMetricValue"] {color: #0B5394;}
  [data-testid="stSidebar"] {background: #EAF3FB;}
  .block-container {padding-top: 4rem; max-width: 1320px;}
  [data-testid="stMetricValue"] {font-size: 1.9rem;}
  [data-testid="stMetricLabel"] p {white-space: normal; overflow: visible;}
</style>""", unsafe_allow_html=True)

vistas.PAGINA_RESPUESTA = st.Page(vistas.respuesta, title="La respuesta: qué comprar y qué trasladar", icon=":material/task_alt:",
                                  url_path="respuesta")
paginas = {
    "Resumen": [st.Page(vistas.inicio, title="Inicio", icon=":material/home:", default=True),
                vistas.PAGINA_RESPUESTA],
    "Las 6 preguntas": [
        st.Page(vistas.p1, title="1 · El inventario en 2025", icon=":material/trending_down:", url_path="p1-inventario"),
        st.Page(vistas.p2, title="2 · ¿90 % de abastecimiento?", icon=":material/fact_check:", url_path="p2-abastecimiento"),
        st.Page(vistas.p3, title="3 · Quiénes pagan", icon=":material/groups:", url_path="p3-pacientes"),
        st.Page(vistas.p4, title="4 · El interior", icon=":material/local_shipping:", url_path="p4-redistribucion"),
        st.Page(vistas.p5, title="5 · La Comisión", icon=":material/account_balance:", url_path="p5-comision"),
        st.Page(vistas.p6, title="6 · Medicamentos fantasma", icon=":material/inventory_2:", url_path="p6-fantasmas"),
    ],
    "IA generativa": [st.Page(asistente.pagina, title="Pregúntale a los datos", icon=":material/chat:", url_path="asistente")],
}
try:
    nav = st.navigation(paginas)
    vistas.filtros()
    nav.run()
except Exception as e:  # datos aún no publicados o fuente caída: aviso en lugar de error técnico
    st.warning("Los datos de esta página todavía se están generando o la fuente no responde. "
                "Intenta de nuevo en unos minutos.")
    with st.expander("Detalle técnico"):
        st.code(f"{type(e).__name__}: {e}")
st.sidebar.caption("Proyecto final · Sistemas de Información Gerencial · UTP 2026")
st.sidebar.caption("[Código en GitHub](https://github.com/1ZH13/css-pharma-supply-analytics)")
