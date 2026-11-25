"""Páginas del dashboard: una por cada pregunta del proyecto."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import datos

# Paleta institucional: azules de la Caja de Seguro Social
AZUL, MARINO, CELESTE = "#0B5394", "#0A2F5C", "#3DA5D9"
GRIS, ROJO, VERDE, AMBAR = "#7F8C9A", "#C0392B", "#2E7D5B", "#E08E0B"
PAGINA_RESPUESTA = None  # la fija app.py con el objeto st.Page de la respuesta
CENTRO = {"CDPA": "Panamá (CDPA)", "CDDI": "Divisa (CDDI)", "CDCH": "Chiriquí (CDCH)"}
COLOR_CENTRO = {"CDPA": AZUL, "CDDI": AMBAR, "CDCH": CELESTE}


# ------------------------------------------------------------- Filtros globales
def filtros():
    """Segmentadores de la barra lateral: centro, grupo de pacientes y rango de meses.
    Se guardan en st.session_state y cada página los aplica donde tienen sentido."""
    k = datos.tabla("kpi_mensual")
    periodos = sorted(k["periodo"].astype(str).unique())
    grupos = sorted(datos.tabla("riesgo_medicamentos")["categoria_critica"].dropna().unique())
    with st.sidebar:
        st.markdown("**Filtros**")
        st.multiselect("Centro de distribución", list(CENTRO), default=list(CENTRO), format_func=CENTRO.get, key="f_centros")
        st.multiselect("Grupo de pacientes", grupos, key="f_grupos", placeholder="Todos los grupos")
        st.select_slider("Meses", options=periodos, value=(periodos[0], periodos[-1]), key="f_meses")


def _f_centros() -> list[str]:
    return st.session_state.get("f_centros") or list(CENTRO)


def _f_grupos() -> list[str]:
    return st.session_state.get("f_grupos") or []


def _f_meses(df: pd.DataFrame, col: str = "periodo") -> pd.DataFrame:
    a, b = st.session_state.get("f_meses", (None, None))
    if a is None:
        return df
    x = df[col].astype(str).str[:7]
    return df[(x >= a) & (x <= b)]


def _filtro_activo() -> str:
    partes = []
    if len(_f_centros()) < len(CENTRO):
        partes.append(", ".join(_f_centros()))
    if _f_grupos():
        partes.append(", ".join(_f_grupos()))
    a, b = st.session_state.get("f_meses", (None, None))
    if a:
        partes.append(f"{a} a {b}")
    return " · ".join(partes)


def _fig(fig, alto=380):
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white",
                      font=dict(family="sans-serif", size=13), legend=dict(orientation="h", y=-0.2),
                      hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E6EEF5")
    return fig


def _b(x, d=1):
    return f"B/. {x / 1e6:,.{d}f} M" if abs(x) >= 1e6 else f"B/. {x:,.0f}"


def _encabezado(pid: str):
    n = datos.documento("narrativa")["preguntas"][pid]
    st.caption(f"{pid} · {n['pregunta']}")
    st.title(n["titular"])
    st.write(n["hallazgo"])
    c1, c2 = st.columns(2)
    c1.info(f"**Decisión:** {n['implicacion']}")
    c2.warning(f"**Cautela:** {n['cautela']}")
    return n


def _pie(fuente: str):
    st.divider()
    nar = datos.documento("narrativa")
    ia = f" · Texto redactado por {nar.get('modelo')}" if nar.get("origen") == "gemini" else ""
    st.caption(f"Fuente: {fuente}. Datos leídos desde {datos.origen()}{ia}.")


# ------------------------------------------------------------------ Inicio
def inicio():
    k = datos.documento("kpi_resumen")
    nar = datos.documento("narrativa")
    st.caption(f"Sistema de Información Gerencial · Inventario de medicamentos de la Caja de Seguro Social · corte {k['periodo']}")
    st.title("¿Qué medicamentos están en riesgo y cómo redistribuirlos?")
    c = st.columns(4)
    c[0].metric("Abastecimiento (almacenes)", f"{k['pct_abastecimiento']} %", help="Renglones con existencia nacional > 0")
    c[1].metric("Críticos sin existencia", k["criticos_en_cero"], help="Insulinas, oncológicos, VIH, cardiovascular…")
    c[2].metric("En riesgo alto", k["riesgo_alto"], f"{k['criticos_riesgo_alto']} críticos", delta_color="off")
    c[3].metric("Valor del inventario", _b(k["valor_inventario"]), f"{k['variacion_valor_12m_pct']} % en 12 meses", delta_color="off")

    if PAGINA_RESPUESTA is not None:
        st.page_link(PAGINA_RESPUESTA, label="Ver el plan de acción: qué comprar ya, qué reforzar y qué trasladar →", icon=":material/task_alt:")
    st.subheader("Seis hallazgos que llevan a la respuesta")
    cols = st.columns(3)
    for i, (pid, n) in enumerate(nar["preguntas"].items()):
        with cols[i % 3].container(border=True):
            st.caption(f"{pid} · {n['pregunta']}")
            st.markdown(f"**{n['titular']}**")

    with st.expander("Cómo funciona el sistema"):
        st.graphviz_chart("""
        digraph { rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#EAF3FB", color="#0B5394", fontname="sans-serif"];
          a [label="CSS · 79 CSV\\n(datosabiertos.gob.pa)"]; b [label="openFDA\\n(JSON)"]; c [label="21 noticias e informes\\n(texto)"];
          p [label="GitHub Actions\\nextracción → limpieza → calidad", fillcolor="#D3E7F6"];
          ia [label="Gemini\\n(IA generativa)", fillcolor="#FCEFD9"]; k [label="KPI · riesgo ·\\nredistribución"];
          m [label="MongoDB Atlas", fillcolor="#DDEFE6"]; d [label="Dashboards\\nStreamlit · Power BI"];
          a -> p; b -> p; c -> p; p -> ia; p -> k; ia -> k; k -> m; ia -> m; m -> d; }""")
        st.caption("Se actualiza solo el día 3 de cada mes. 109 893 registros validados al 99.95–100 % contra los cuadros oficiales de la CSS.")
    _pie("Dirección Nacional de Logística de la CSS (datos abiertos), openFDA, prensa nacional")


# --------------------------------------------------------------------- P1
def p1():
    _encabezado("P1")
    r = datos.documento("preguntas_resumen")["P1"]
    s = _f_meses(datos.tabla("p1_serie").sort_values("periodo"))
    c = st.columns(4)
    c[0].metric("Cambio en cantidad", f"{r['cambio_cantidad_pct']} %", help=f"Mismos {r['medicamentos_comparados']} medicamentos, {r['corte']}")
    c[1].metric("Cambio en valor", f"{r['cambio_valor_pct']} %")
    c[2].metric("Cambio de precio (mediana)", f"× {r['cambio_precio_mediano']}", help="1.0 = los precios no cambiaron")
    c[3].metric("Valor promedio mensual", f"B/. {r['valor_mensual_promedio_M']['2024']} M → {r['valor_mensual_promedio_M']['2026']} M",
                help="2024 → 2026")
    medida = st.radio("Ver", ["Valor (B/.)", "Unidades"], horizontal=True, label_visibility="collapsed")
    col, colc = ("valor", "valor_canasta") if medida.startswith("Valor") else ("cantidad", "cantidad_canasta")
    fig = go.Figure()
    fig.add_scatter(x=s["periodo"], y=s[col], name="Todo el inventario", line=dict(color=AZUL, width=3))
    fig.add_scatter(x=s["periodo"], y=s[colc], name=f"Canasta fija ({r['canasta_fija_medicamentos']} medicamentos)",
                    line=dict(color=GRIS, dash="dot"))
    fig.add_vrect(x0="2024-10", x1="2025-01", fillcolor=ROJO, opacity=0.12, line_width=0, annotation_text="corte")
    st.plotly_chart(_fig(fig), width="stretch")

    st.subheader("Apoyo: dinero inmovilizado")
    st.write(f"Aun con menos inventario, **{_b(r['inmovilizado_mas_12_meses_M'] * 1e6, 2)} ({r['inmovilizado_pct_del_valor']} % del valor)** "
             f"está en **{r['inmovilizado_medicamentos']} medicamentos con más de 12 meses de cobertura**: dinero que no rota y puede vencerse.")
    rg = datos.tabla("riesgo_medicamentos")
    inm = rg[rg["cobertura_meses"] > 12].sort_values("valor_existencia", ascending=False)
    st.dataframe(inm[["descripcion", "existencia_total", "consumo_mensual_est", "cobertura_meses", "valor_existencia"]].head(15),
                 hide_index=True, width="stretch",
                 column_config={"descripcion": "Medicamento", "existencia_total": st.column_config.NumberColumn("Existencia", format="%,d"),
                                "consumo_mensual_est": st.column_config.NumberColumn("Consumo/mes (est.)", format="%,d"),
                                "cobertura_meses": st.column_config.NumberColumn("Cobertura (meses)", format="%.0f"),
                                "valor_existencia": st.column_config.NumberColumn("Valor (B/.)", format="%,.0f")})
    _pie("Inventario mensual de medicamentos de la CSS, 2021–2026")


# --------------------------------------------------------------------- P2
def p2():
    _encabezado("P2")
    r = datos.documento("preguntas_resumen")["P2"]
    k = _f_meses(datos.tabla("kpi_mensual").sort_values("periodo"))
    d = datos.tabla("p2_declaraciones")
    c = st.columns(3)
    c[0].metric("Lo que se anuncia", f"{r['pct_declarado_min']:.0f}–{r['pct_declarado_max']:.0f} %", help=f"{r['declaraciones']} declaraciones en prensa (extraídas por IA)")
    c[1].metric("Lo que muestran los datos", f"{r['pct_datos_12m_min']}–{r['pct_datos_12m_max']} %", help="Últimos 12 meses")
    c[2].metric("Brecha promedio", f"{r['brecha_promedio_pp']} p.p." if r.get("brecha_promedio_pp") is not None else "—")
    fig = go.Figure()
    fig.add_scatter(x=k["periodo"], y=k["pct_abastecimiento"], name="Datos de la CSS (almacenes)", line=dict(color=AZUL, width=3))
    dd = d.dropna(subset=["fecha"])
    if len(dd):
        fig.add_scatter(x=dd["fecha"], y=dd["pct_declarado"], mode="markers+text", name="Declarado en prensa",
                        marker=dict(size=14, color=ROJO, symbol="diamond"), text=dd["fuente"], textposition="top center",
                        customdata=dd[["titulo"]], hovertemplate="%{customdata[0]}<br>%{y} %<extra></extra>")
    fig.add_hline(y=90, line_dash="dot", line_color=GRIS, annotation_text="90 %")
    fig.update_yaxes(range=[60, 100], ticksuffix=" %")
    st.plotly_chart(_fig(fig), width="stretch")
    st.subheader("Las declaraciones (leídas por IA)")
    for x in d.itertuples():
        with st.container(border=True):
            st.markdown(f"**{x.pct_declarado:.0f} %** · {x.fuente} · {x.fecha or 's/f'} — [{x.titulo}]({x.url})")
            st.caption(x.resumen_ia)
    _pie("Inventario CSS; noticias de La Estrella, Telemetro, TVN y Panamá América analizadas con Gemini")


# --------------------------------------------------------------------- P3
def p3():
    _encabezado("P3")
    r = datos.documento("preguntas_resumen")["P3"]
    g = datos.tabla("p3_grupos").sort_values("pct_meses_en_cero")
    colores = [GRIS if x == "No crítico" else (ROJO if v > r["pct_no_criticos"] else AZUL) for x, v in zip(g["grupo"], g["pct_meses_en_cero"])]
    fig = go.Figure(go.Bar(x=g["pct_meses_en_cero"], y=g["grupo"], orientation="h", marker_color=colores,
                           text=g["pct_meses_en_cero"].map(lambda v: f"{v} %"), textposition="outside"))
    fig.add_vline(x=r["pct_no_criticos"], line_dash="dot", line_color=GRIS, annotation_text="no críticos")
    fig.update_xaxes(title=f"% de meses sin existencia ({r['ventana']})", ticksuffix=" %")
    st.plotly_chart(_fig(fig, 430), width="stretch")
    if r.get("criticos_con_escasez_eeuu"):
        st.caption(f"Apoyo internacional: {r['criticos_con_escasez_eeuu']} medicamentos críticos de la CSS también están hoy en escasez en EE. UU. "
                   "(openFDA): ahí el problema es global, no solo local.")
    st.subheader("Medicamentos críticos en riesgo alto")
    rg = datos.tabla("riesgo_medicamentos")
    rg = rg[rg["critico"].astype(bool) & (rg["nivel_riesgo"] == "alto")]
    if _f_grupos():
        rg = rg[rg["categoria_critica"].isin(_f_grupos())]
        st.caption(f"Filtrado por: {', '.join(_f_grupos())} (barra lateral)")
    st.dataframe(rg[["descripcion", "categoria_critica", "existencia_total", "cobertura_meses", "puntaje_riesgo", "escasez_eeuu", "motivos"]],
                 hide_index=True, width="stretch",
                 column_config={"descripcion": "Medicamento", "categoria_critica": "Grupo",
                                "existencia_total": st.column_config.NumberColumn("Existencia", format="%,d"),
                                "cobertura_meses": st.column_config.NumberColumn("Cobertura (meses)", format="%.1f"),
                                "puntaje_riesgo": st.column_config.ProgressColumn("Riesgo", min_value=0, max_value=100, format="%d"),
                                "escasez_eeuu": st.column_config.CheckboxColumn("Escasez EE. UU."), "motivos": "Por qué"})
    _pie("Inventario CSS (últimos 12 meses), clasificación ATC, openFDA Drug Shortages")


# --------------------------------------------------------------------- P4
def p4():
    _encabezado("P4")
    r = datos.documento("preguntas_resumen")["P4"]
    c = datos.tabla("p4_centros")
    c["Centro"] = c["centro"].map(CENTRO)
    a, b = st.columns(2)
    f1 = px.pie(c, names="Centro", values="valor", hole=0.55, color="centro", color_discrete_map=COLOR_CENTRO)
    f1.update_traces(textinfo="percent+label", showlegend=False)
    a.markdown("**Participación en el valor del inventario**")
    a.plotly_chart(_fig(f1, 320), width="stretch")
    f2 = go.Figure(go.Bar(x=c["Centro"], y=c["pct_en_cero_con_stock_en_otro"], marker_color=[COLOR_CENTRO[x] for x in c["centro"]],
                          text=c["pct_en_cero_con_stock_en_otro"].map(lambda v: f"{v} %"), textposition="outside"))
    f2.update_yaxes(ticksuffix=" %")
    b.markdown("**Renglones en cero aunque otro centro sí tiene**")
    b.plotly_chart(_fig(f2, 320), width="stretch")

    st.subheader(f"{r['transferencias']} traslados sugeridos · {_b(r['valor_transferencias_M'] * 1e6, 2)} · {r['transferencias_criticos']} de medicamentos críticos")
    rutas = datos.tabla("p4_rutas")
    if len(rutas):
        nodos = [f"{CENTRO[x]} (cede)" for x in CENTRO] + [f"{CENTRO[x]} (recibe)" for x in CENTRO]
        idx = {**{x: i for i, x in enumerate(CENTRO)}, **{x + "_r": i + 3 for i, x in enumerate(CENTRO)}}
        fig = go.Figure(go.Sankey(node=dict(label=nodos, color=[COLOR_CENTRO[x] for x in CENTRO] * 2, pad=20),
                                  link=dict(source=[idx[x] for x in rutas["desde"]], target=[idx[x + "_r"] for x in rutas["hacia"]],
                                            value=rutas["valor"], customdata=rutas["transferencias"],
                                            hovertemplate="%{customdata} traslados · B/. %{value:,.0f}<extra></extra>")))
        st.plotly_chart(_fig(fig, 320), width="stretch")
    red = datos.tabla("redistribucion")
    f = st.columns(3)
    solo = f[0].toggle("Solo críticos", value=True)
    hacia = f[1].multiselect("Centro que recibe", list(CENTRO), default=_f_centros(), format_func=CENTRO.get)
    q = f[2].text_input("Buscar medicamento")
    v = red[red["hacia"].isin(hacia)]
    if solo:
        v = v[v["critico"].astype(bool)]
    if q:
        v = v[v["descripcion"].str.contains(q, case=False, na=False)]
    if _f_grupos():
        cat = datos.tabla("riesgo_medicamentos").set_index("codigo")["categoria_critica"]
        v = v[v["codigo"].map(cat).isin(_f_grupos())]
    st.dataframe(v[["descripcion", "desde", "hacia", "cantidad", "valor", "cobertura_destino_antes", "cobertura_destino_despues"]],
                 hide_index=True, width="stretch",
                 column_config={"descripcion": "Medicamento", "desde": "Desde", "hacia": "Hacia",
                                "cantidad": st.column_config.NumberColumn("Cantidad", format="%,d"),
                                "valor": st.column_config.NumberColumn("Valor (B/.)", format="%,.0f"),
                                "cobertura_destino_antes": st.column_config.NumberColumn("Cobertura destino antes", format="%.1f m"),
                                "cobertura_destino_despues": st.column_config.NumberColumn("después", format="%.1f m")})
    st.download_button("Descargar órdenes de traslado (CSV)", v.to_csv(index=False).encode("utf-8-sig"), "traslados_sugeridos.csv", "text/csv")
    _pie("Inventario CSS por centro de distribución; regla: recibe < 1 mes, cede > 4 meses, objetivo 2 meses")


# --------------------------------------------------------------------- P5
def p5():
    _encabezado("P5")
    r = datos.documento("preguntas_resumen")["P5"]
    k = datos.tabla("kpi_mensual").sort_values("periodo")
    k = _f_meses(k[k["periodo"] >= "2024-01"])
    c = st.columns(3)
    c[0].metric("Abastecimiento", f"{r['abastecimiento_ultimo_pct']} %", f"{r['abastecimiento_ultimo_pct'] - r['abastecimiento_en_hito_pct']:+.1f} p.p. desde oct-2025")
    c[1].metric("Críticos sin existencia", r["criticos_en_cero_ultimo"], f"{r['criticos_en_cero_ultimo'] - r['criticos_en_cero_en_hito']:+d} desde oct-2025", delta_color="inverse")
    c[2].metric("Promedio 6 meses antes → últimos 6", f"{r['abastecimiento_antes_pct']} % → {r['abastecimiento_despues_pct']} %")
    fig = go.Figure()
    fig.add_scatter(x=k["periodo"], y=k["pct_abastecimiento"], name="% abastecimiento", line=dict(color=AZUL, width=3))
    fig.add_bar(x=k["periodo"], y=k["criticos_en_cero"], name="Críticos en cero", marker_color=ROJO, opacity=0.35, yaxis="y2")
    fig.add_vline(x=r["hito"], line_dash="dash", line_color=VERDE)
    fig.add_annotation(x=r["hito"], y=1.02, yref="paper", text="Comisión de Desabastecimiento Crítico", showarrow=False, font=dict(color=VERDE))
    fig.update_layout(yaxis=dict(ticksuffix=" %", range=[60, 100]), yaxis2=dict(overlaying="y", side="right", showgrid=False, title="críticos en cero"))
    st.plotly_chart(_fig(fig, 420), width="stretch")
    ev = datos.tabla("p5_eventos")
    if len(ev):
        st.subheader("Línea de tiempo (noticias leídas por IA)")
        for x in ev[ev["fecha"] >= "2025"].sort_values("fecha", ascending=False).itertuples():
            st.markdown(f"- **{x.fecha}** · {x.fuente} · _{str(x.tipo_evento).replace('_', ' ')}_ — [{x.titulo}]({x.url})")
    _pie("Inventario CSS; noticias analizadas con Gemini")


# --------------------------------------------------------------------- P6
def p6():
    _encabezado("P6")
    f = datos.tabla("p6_fantasmas")
    q = st.text_input("Buscar medicamento", placeholder="p. ej. melfalano")
    v = f[f["descripcion"].str.contains(q, case=False, na=False)] if q else f
    if _f_grupos():
        v = v[v["categoria_critica"].isin(_f_grupos())]
    st.dataframe(v[["descripcion", "categoria_critica", "grupo_terapeutico", "ultimo_mes_con_existencia", "precio_ultimo"]],
                 hide_index=True, width="stretch",
                 column_config={"descripcion": "Medicamento", "categoria_critica": "Crítico", "grupo_terapeutico": "Grupo ATC",
                                "ultimo_mes_con_existencia": "Última vez con existencia", "precio_ultimo": st.column_config.NumberColumn("Precio (B/.)", format="%.2f")})
    sel = st.selectbox("Ver historia de un medicamento", v["descripcion"].tolist())
    if sel:
        cod = v.loc[v["descripcion"] == sel, "codigo"].iloc[0]
        h = datos.historia(cod)
        if len(h):
            fig = px.bar(h.sort_values("periodo"), x="periodo", y="cantidad", color="centro", color_discrete_map=COLOR_CENTRO,
                         labels={"cantidad": "Existencia", "periodo": ""})
            st.plotly_chart(_fig(fig, 300), width="stretch")
    _pie("Inventario CSS: renglones publicados en el último corte con 12 meses consecutivos en cero")


# --------------------------------------------------------------- Respuesta
ACCIONES = {"Comprar ya": ROJO, "Reforzar compra": AMBAR, "Trasladar": AZUL, "Vigilar": CELESTE, "Sin acción": GRIS}


def plan_de_accion() -> pd.DataFrame:
    """Clasifica cada medicamento en una acción concreta (es la respuesta a la pregunta gerencial).

    - Comprar ya: riesgo alto y sin existencia en ningún almacén (trasladar no sirve).
    - Reforzar compra: riesgo alto con menos de 1 mes de cobertura; ningún centro tiene sobrante.
    - Trasladar: tiene un traslado sugerido (un centro con más de 4 meses cede a otro con menos de 1).
    - Vigilar: riesgo medio sin traslado.
    """
    rg = datos.tabla("riesgo_medicamentos").copy()
    red = datos.tabla("redistribucion")
    rg["critico"] = rg["critico"].astype(str).str.lower().isin(["true", "1"])
    rg["escasez_eeuu"] = rg["escasez_eeuu"].astype(str).str.lower().isin(["true", "1"])
    con_traslado = set(red["codigo"].astype(str))
    alto = rg["nivel_riesgo"] == "alto"
    rg["accion"] = "Sin acción"
    rg.loc[rg["nivel_riesgo"] == "medio", "accion"] = "Vigilar"
    rg.loc[rg["codigo"].isin(con_traslado), "accion"] = "Trasladar"
    rg.loc[alto & (rg["existencia_total"] > 0), "accion"] = "Reforzar compra"
    rg.loc[alto & (rg["existencia_total"] <= 0), "accion"] = "Comprar ya"
    rg["grupo"] = rg["categoria_critica"].fillna("No crítico")
    return rg


def respuesta():
    k = datos.documento("kpi_resumen")
    r = datos.documento("preguntas_resumen")
    rg = plan_de_accion()
    red = datos.tabla("redistribucion")
    red["critico"] = red["critico"].astype(str).str.lower().isin(["true", "1"])
    if _f_grupos():
        rg = rg[rg["grupo"].isin(_f_grupos())]
        red = red[red["codigo"].isin(rg["codigo"])]
    red = red[red["hacia"].isin(_f_centros())]

    alto = rg[rg["nivel_riesgo"] == "alto"]
    crit = alto[alto["critico"]]
    comprar = crit[crit["accion"] == "Comprar ya"]
    reforzar = crit[crit["accion"] == "Reforzar compra"]

    st.caption(f"Respuesta a la pregunta gerencial · corte {k['periodo']}"
               + (f" · filtro: {_filtro_activo()}" if _filtro_activo() else ""))
    st.title("¿Qué medicamentos están en riesgo de desabastecimiento y cómo redistribuir el inventario?")
    st.markdown(
        f"**Respuesta corta.** Hay **{len(alto)} medicamentos en riesgo alto; {len(crit)} son críticos** "
        f"(oncológicos, cardiovasculares, asma/EPOC, VIH…). A esos no los salva un traslado: "
        f"**{len(comprar)} no tienen existencia en ningún almacén** y **{len(reforzar)} tienen menos de un mes** "
        f"sin que otro centro tenga sobrante, así que se **compran**. La **redistribución** sirve para lo que sí "
        f"tiene sobrante: **{len(red)} traslados ({_b(red['valor'].sum(), 2)})** de centros con más de 4 meses de "
        f"cobertura a centros con menos de 1 ({int(red['hacia'].isin(['CDDI', 'CDCH']).sum())} hacia Divisa y Chiriquí, "
        f"{int((red['hacia'] == 'CDPA').sum())} hacia Panamá), que evitan nuevos quiebres.")

    c = st.columns(4)
    c[0].metric("Críticos en riesgo alto", len(crit), f"de {len(alto)} en riesgo alto", delta_color="off")
    c[1].metric("Comprar ya", len(comprar), "sin existencia en ningún almacén", delta_color="off")
    c[2].metric("Reforzar compra", len(reforzar), "menos de 1 mes de cobertura", delta_color="off")
    c[3].metric("Trasladar", len(red), f"{_b(red['valor'].sum(), 2)} · {int(red['critico'].sum())} críticos", delta_color="off")

    # ---------------------------------------------------------- 1. Qué medicamentos
    st.subheader("1 · Qué medicamentos: los críticos en riesgo alto, por grupo de pacientes")
    g = crit.groupby(["grupo", "accion"]).size().reset_index(name="n")
    if len(g):
        orden = g.groupby("grupo")["n"].sum().sort_values().index.tolist()
        fig = px.bar(g, x="n", y="grupo", color="accion", orientation="h", color_discrete_map=ACCIONES,
                     category_orders={"grupo": orden, "accion": list(ACCIONES)}, labels={"n": "Medicamentos", "grupo": "", "accion": ""})
        st.plotly_chart(_fig(fig, 360), width="stretch")
    eeuu = int(crit["escasez_eeuu"].sum())
    if eeuu:
        st.caption(f"{eeuu} de estos críticos también están hoy en escasez en EE. UU. (openFDA): para ellos conviene buscar "
                   "proveedor alterno o sustituto terapéutico, porque el problema es del mercado global.")
    ver = st.radio("Lista", ["Críticos en riesgo alto", "Todos en riesgo alto"], horizontal=True, label_visibility="collapsed")
    todos = not ver.startswith("Críticos")
    lista = (alto if todos else crit).sort_values(["critico", "accion", "puntaje_riesgo"], ascending=[False, True, False])
    if todos:
        fantasmas = set(datos.tabla("p6_fantasmas")["codigo"].astype(str))
        nc = lista[~lista["critico"]]
        st.caption(f"Mostrando los {len(lista)} medicamentos en riesgo alto: {int(lista['critico'].sum())} críticos (arriba) y "
                   f"{len(nc)} no críticos, de los cuales {int(nc['codigo'].astype(str).isin(fantasmas).sum())} son medicamentos fantasma (P6).")
    else:
        st.caption(f"Mostrando los {len(lista)} medicamentos críticos en riesgo alto. Elige «Todos en riesgo alto» para ver también los no críticos.")
    cols = (["accion", "descripcion", "grupo"] + (["critico"] if todos else []) + [f"existencia_{x}" for x in _f_centros()]
            + ["cobertura_meses", "escasez_eeuu", "puntaje_riesgo"])
    st.dataframe(lista[cols], hide_index=True, width="stretch",
                 column_config={"accion": st.column_config.TextColumn("Acción", width="small"),
                                "descripcion": st.column_config.TextColumn("Medicamento", width="large"),
                                "grupo": st.column_config.TextColumn("Grupo", width="medium"),
                                "critico": st.column_config.CheckboxColumn("Crítico", width="small"),
                                **{f"existencia_{x}": st.column_config.NumberColumn(x, format="%,d", width="small") for x in CENTRO},
                                "cobertura_meses": st.column_config.NumberColumn("Meses", format="%.2f", width="small",
                                                                                 help="Cobertura en meses al consumo estimado"),
                                "escasez_eeuu": st.column_config.CheckboxColumn("EE. UU.", width="small", help="También en escasez en EE. UU. (openFDA)"),
                                "puntaje_riesgo": st.column_config.ProgressColumn("Riesgo", min_value=0, max_value=100, format="%d", width="small")})
    st.download_button("Descargar lista de compras y refuerzos (CSV)", lista[cols].to_csv(index=False).encode("utf-8-sig"),
                       "medicamentos_en_riesgo.csv", "text/csv")

    # ---------------------------------------------------------- 2. Cómo redistribuir
    st.subheader("2 · Cómo redistribuir: quién cede y quién recibe")
    a, b = st.columns([3, 2])
    rutas = (red.groupby(["desde", "hacia"]).agg(traslados=("valor", "size"), criticos=("critico", "sum"), valor=("valor", "sum"))
             .reset_index().sort_values("valor", ascending=False))
    rutas["Ruta"] = rutas["desde"].map(CENTRO) + " → " + rutas["hacia"].map(CENTRO)
    fig = px.bar(rutas, x="valor", y="Ruta", orientation="h", color="hacia", color_discrete_map=COLOR_CENTRO,
                 text=rutas["traslados"].map(lambda n: f"{n} traslados"), labels={"valor": "Valor trasladado (B/.)", "Ruta": ""})
    fig.update_traces(textposition="inside")
    fig.update_layout(showlegend=False)
    a.plotly_chart(_fig(fig, 320), width="stretch")
    rg_todo = plan_de_accion()
    regla = []
    for x in ("CDDI", "CDCH", "CDPA"):
        en_cero = rg_todo[rg_todo["critico"] & (rg_todo[f"existencia_{x}"] <= 0) & (rg_todo["existencia_total"] > 0)]
        regla.append({"Centro": CENTRO[x], "Críticos en cero con existencia en otro centro": len(en_cero),
                      "Con traslado sugerido": int(en_cero["codigo"].isin(datos.tabla("redistribucion").query("hacia == @x")["codigo"]).sum())})
    b.markdown("**Regla de reparto mínimo**")
    b.dataframe(pd.DataFrame(regla), hide_index=True, width="stretch")
    b.caption("La mayoría de esos críticos no recibe traslado porque el centro que los tiene quedaría corto. "
              "Por eso se propone un reparto mínimo de 2 meses por almacén en cada compra nueva.")

    # ---------------------------------------------------------- 3. Qué decidir
    st.subheader("3 · Qué decidir este mes")
    p1, p3, p6 = r["P1"], r["P3"], r["P6"]
    eeuu_comprar = int(comprar['escasez_eeuu'].sum())
    recs = [
        ("Comprar ya", ROJO, f"Compra urgente o conjunta (Comisión de Desabastecimiento Crítico) de los **{len(comprar)} críticos sin existencia**"
                             + (f"; proveedor alterno o sustituto para los {eeuu_comprar} que también escasean en EE. UU." if eeuu_comprar else ".")),
        ("Reforzar", AMBAR, f"Adelantar la compra de los **{len(reforzar)} críticos con menos de 1 mes** y fijar stock de seguridad "
                            f"por grupo de pacientes, empezando por {', '.join(x['grupo'] for x in p3['top3'][:2]).lower()}."),
        ("Trasladar", AZUL, f"Ejecutar los **{len(red)} traslados** ({_b(red['valor'].sum(), 2)}) antes de comprar, y repartir cada compra "
                            "nueva con un mínimo de 2 meses por almacén."),
        ("Financiar", VERDE, f"Liberar presupuesto revisando los **{_b(p1['inmovilizado_mas_12_meses_M'] * 1e6, 2)} inmovilizados** en "
                             f"{p1['inmovilizado_medicamentos']} medicamentos con más de 12 meses de cobertura, y depurar los "
                             f"**{p6['fantasmas']} medicamentos fantasma** del catálogo."),
    ]
    cols = st.columns(4)
    for col, (t, color, txt) in zip(cols, recs):
        with col.container(border=True):
            st.markdown(f"<span style='color:{color};font-weight:700'>{t}</span>", unsafe_allow_html=True)
            st.markdown(txt)

    with st.expander("Cómo llegan las 6 preguntas a esta respuesta"):
        st.markdown(f"""
- **P1 · Por qué pasó:** el inventario cayó {abs(p1['cambio_valor_pct'])} % en valor (oct-24 → ene-25) y aun así hay {_b(p1['inmovilizado_mas_12_meses_M'] * 1e6, 2)} inmovilizados → de ahí sale el dinero.
- **P2 · Cómo medirlo:** el abastecimiento real de los almacenes es {r['P2']['pct_datos_ultimo']} %, no el 90–96 % anunciado → el indicador para dar seguimiento.
- **P3 · A quién afecta:** asma/EPOC, oncológicos y VIH pasan más meses en cero → el orden de prioridad de la compra.
- **P4 · Dónde falta:** Divisa y Chiriquí tienen en cero 23–27 % de lo que otro centro tiene → los traslados y el reparto mínimo.
- **P5 · Qué ya funciona:** desde la Comisión el abastecimiento subió de {r['P5']['abastecimiento_en_hito_pct']} % a {r['P5']['abastecimiento_ultimo_pct']} % → el canal para comprar.
- **P6 · Qué depurar:** {p6['fantasmas']} medicamentos llevan 12 meses en cero → reactivar, sustituir o retirar del catálogo.
""")
    _pie("Inventario CSS por centro (riesgo y redistribución calculados por el pipeline), openFDA")

# ------------------------------------------------------- Ficha de medicamento
def ficha():
    """Consulta de un medicamento: existencias por centro, riesgo, acción sugerida e historia mensual."""
    k = datos.documento("kpi_resumen")
    rg = plan_de_accion()
    if _f_grupos():
        rg = rg[rg["grupo"].isin(_f_grupos())]
    rg = rg.sort_values("puntaje_riesgo", ascending=False)
    st.caption(f"Consulta por medicamento · corte {k['periodo']}"
               + (f" · filtro: {_filtro_activo()}" if _filtro_activo() else ""))
    st.title("Ficha de medicamento")
    st.write("Busca cualquier medicamento del catálogo publicado para ver cuánto hay en cada almacén, "
             "cuánto dura, por qué tiene ese nivel de riesgo y qué acción le corresponde.")
    if rg.empty:
        st.info("No hay medicamentos con el filtro de grupo elegido.")
        return
    opciones = rg["codigo"].tolist()
    nombres = dict(zip(rg["codigo"], rg["descripcion"]))
    cod = st.selectbox("Medicamento (escribe para buscar)", opciones, format_func=lambda c: f"{nombres[c]} · {c}")
    m = rg[rg["codigo"] == cod].iloc[0]

    st.subheader(m["descripcion"])
    accion = m["accion"]
    etiquetas = [f"<span style='background:{ACCIONES.get(accion, GRIS)};color:white;padding:3px 10px;border-radius:12px;"
                 f"font-weight:600'>{accion}</span>",
                 f"<span style='background:#E3F0FA;color:{AZUL};padding:3px 10px;border-radius:12px'>"
                 f"Riesgo {m['nivel_riesgo']} · {int(m['puntaje_riesgo'])}/100</span>",
                 f"<span style='background:#E3F0FA;color:{AZUL};padding:3px 10px;border-radius:12px'>"
                 + (f"Crítico: {m['grupo']}" if m["critico"] else "No crítico") + "</span>"]
    if m["escasez_eeuu"]:
        etiquetas.append(f"<span style='background:#FBE9E7;color:{ROJO};padding:3px 10px;border-radius:12px'>"
                         "También escasea en EE. UU.</span>")
    fantasmas = set(datos.tabla("p6_fantasmas")["codigo"].astype(str))
    if str(cod) in fantasmas:
        etiquetas.append("<span style='background:#EEE;color:#333;padding:3px 10px;border-radius:12px'>"
                         "Fantasma: 12 meses en cero</span>")
    st.markdown(" ".join(etiquetas), unsafe_allow_html=True)

    c = st.columns(4)
    c[0].metric("Existencia total", f"{m['existencia_total']:,.0f}")
    c[1].metric("Consumo mensual (est.)", f"{m['consumo_mensual_est']:,.0f}" if pd.notna(m["consumo_mensual_est"]) else "s/d")
    cob = m["cobertura_meses"]
    c[2].metric("Cobertura", f"{cob:,.1f} meses" if pd.notna(cob) and cob < 1000 else ("sin consumo" if pd.isna(cob) else "más de 1000 meses"))
    c[3].metric("Valor en almacén", _b(m["valor_existencia"]) if pd.notna(m.get("valor_existencia")) else "s/d")

    a, b = st.columns([3, 2])
    filas = []
    for x in _f_centros():
        filas.append({"Centro": CENTRO[x], "Existencia": m.get(f"existencia_{x}"), "Consumo/mes (est.)": m.get(f"consumo_{x}"),
                      "Cobertura (meses)": m.get(f"cobertura_{x}")})
    a.markdown("**Por almacén**")
    a.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch",
                column_config={"Existencia": st.column_config.NumberColumn(format="%,d"),
                               "Consumo/mes (est.)": st.column_config.NumberColumn(format="%,d"),
                               "Cobertura (meses)": st.column_config.NumberColumn(format="%.1f")})
    b.markdown("**Por qué tiene este nivel de riesgo**")
    motivos = str(m.get("motivos") or "").strip()
    b.write(motivos if motivos and motivos != "nan" else "Sin señales de riesgo en este corte.")
    b.caption(f"ATC {m.get('atc') if pd.notna(m.get('atc')) else 's/d'} · {m.get('grupo_terapeutico') if pd.notna(m.get('grupo_terapeutico')) else ''}")

    red = datos.tabla("redistribucion")
    t = red[red["codigo"].astype(str) == str(cod)]
    if len(t):
        st.markdown("**Traslados sugeridos**")
        st.dataframe(t[["desde", "hacia", "cantidad", "valor", "cobertura_destino_antes", "cobertura_destino_despues"]],
                     hide_index=True, width="stretch",
                     column_config={"desde": "Desde", "hacia": "Hacia",
                                    "cantidad": st.column_config.NumberColumn("Cantidad", format="%,d"),
                                    "valor": st.column_config.NumberColumn("Valor (B/.)", format="%,.0f"),
                                    "cobertura_destino_antes": st.column_config.NumberColumn("Cobertura destino antes", format="%.1f m"),
                                    "cobertura_destino_despues": st.column_config.NumberColumn("después", format="%.1f m")})

    h = _f_meses(datos.historia(str(cod)))
    h = h[h["centro"].isin(_f_centros())]
    st.markdown("**Existencia mes a mes por almacén**")
    if len(h):
        fig = px.line(h.sort_values("periodo"), x="periodo", y="cantidad", color="centro", markers=True,
                      color_discrete_map=COLOR_CENTRO, labels={"cantidad": "Existencia (unidades)", "periodo": "", "centro": ""})
        st.plotly_chart(_fig(fig, 340), width="stretch")
    else:
        st.info("No hay registros de este medicamento en el rango de meses elegido.")
    _pie("Inventario CSS por centro, riesgo y traslados calculados por el pipeline, openFDA")
