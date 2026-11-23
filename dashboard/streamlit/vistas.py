"""Páginas del dashboard: una por cada pregunta del proyecto."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import datos

VIOLETA, GRIS, ROJO, VERDE, AMBAR = "#5B2C83", "#8A8494", "#B23A48", "#2E7D5B", "#C98A1B"
CENTRO = {"CDPA": "Panamá (CDPA)", "CDDI": "Divisa (CDDI)", "CDCH": "Chiriquí (CDCH)"}
COLOR_CENTRO = {"CDPA": VIOLETA, "CDDI": AMBAR, "CDCH": "#3A7CA5"}


def _fig(fig, alto=380):
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white",
                      font=dict(family="sans-serif", size=13), legend=dict(orientation="h", y=-0.2),
                      hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#EEE")
    return fig


def _b(x, d=1):
    return f"B/. {x / 1e6:,.{d}f} M"


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

    st.subheader("Seis hallazgos")
    cols = st.columns(3)
    for i, (pid, n) in enumerate(nar["preguntas"].items()):
        with cols[i % 3].container(border=True):
            st.caption(f"{pid} · {n['pregunta']}")
            st.markdown(f"**{n['titular']}**")

    with st.expander("Cómo funciona el sistema"):
        st.graphviz_chart("""
        digraph { rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#F3F0F7", color="#5B2C83", fontname="sans-serif"];
          a [label="CSS · 79 CSV\\n(datosabiertos.gob.pa)"]; b [label="openFDA\\n(JSON)"]; c [label="21 noticias e informes\\n(texto)"];
          p [label="GitHub Actions\\nextracción → limpieza → calidad", fillcolor="#E6DDF0"];
          ia [label="Gemini\\n(IA generativa)", fillcolor="#FCEFD9"]; k [label="KPI · riesgo ·\\nredistribución"];
          m [label="MongoDB Atlas", fillcolor="#DDEFE6"]; d [label="Dashboards\\nStreamlit · Power BI"];
          a -> p; b -> p; c -> p; p -> ia; p -> k; ia -> k; k -> m; ia -> m; m -> d; }""")
        st.caption("Se actualiza solo el día 3 de cada mes. 109 893 registros validados al 99.95–100 % contra los cuadros oficiales de la CSS.")
    _pie("Dirección Nacional de Logística de la CSS (datos abiertos), openFDA, prensa nacional")


# --------------------------------------------------------------------- P1
def p1():
    _encabezado("P1")
    r = datos.documento("preguntas_resumen")["P1"]
    s = datos.tabla("p1_serie").sort_values("periodo")
    c = st.columns(4)
    c[0].metric("Cambio en cantidad", f"{r['cambio_cantidad_pct']} %", help=f"Mismos {r['medicamentos_comparados']} medicamentos, {r['corte']}")
    c[1].metric("Cambio en valor", f"{r['cambio_valor_pct']} %")
    c[2].metric("Cambio de precio (mediana)", f"× {r['cambio_precio_mediano']}", help="1.0 = los precios no cambiaron")
    c[3].metric("Valor promedio mensual", f"B/. {r['valor_mensual_promedio_M']['2024']} M → {r['valor_mensual_promedio_M']['2026']} M",
                help="2024 → 2026")
    medida = st.radio("Ver", ["Valor (B/.)", "Unidades"], horizontal=True, label_visibility="collapsed")
    col, colc = ("valor", "valor_canasta") if medida.startswith("Valor") else ("cantidad", "cantidad_canasta")
    fig = go.Figure()
    fig.add_scatter(x=s["periodo"], y=s[col], name="Todo el inventario", line=dict(color=VIOLETA, width=3))
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
    k = datos.tabla("kpi_mensual").sort_values("periodo")
    d = datos.tabla("p2_declaraciones")
    c = st.columns(3)
    c[0].metric("Lo que se anuncia", f"{r['pct_declarado_min']:.0f}–{r['pct_declarado_max']:.0f} %", help=f"{r['declaraciones']} declaraciones en prensa (extraídas por IA)")
    c[1].metric("Lo que muestran los datos", f"{r['pct_datos_12m_min']}–{r['pct_datos_12m_max']} %", help="Últimos 12 meses")
    c[2].metric("Brecha promedio", f"{r['brecha_promedio_pp']} p.p." if r.get("brecha_promedio_pp") is not None else "—")
    fig = go.Figure()
    fig.add_scatter(x=k["periodo"], y=k["pct_abastecimiento"], name="Datos de la CSS (almacenes)", line=dict(color=VIOLETA, width=3))
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
    colores = [GRIS if x == "No crítico" else (ROJO if v > r["pct_no_criticos"] else VIOLETA) for x, v in zip(g["grupo"], g["pct_meses_en_cero"])]
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
    grupo = st.selectbox("Grupo de pacientes", ["Todos"] + sorted(rg["categoria_critica"].dropna().unique()))
    if grupo != "Todos":
        rg = rg[rg["categoria_critica"] == grupo]
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
    hacia = f[1].multiselect("Centro que recibe", list(CENTRO), default=list(CENTRO), format_func=CENTRO.get)
    q = f[2].text_input("Buscar medicamento")
    v = red[red["hacia"].isin(hacia)]
    if solo:
        v = v[v["critico"].astype(bool)]
    if q:
        v = v[v["descripcion"].str.contains(q, case=False, na=False)]
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
    k = k[k["periodo"] >= "2024-01"]
    c = st.columns(3)
    c[0].metric("Abastecimiento", f"{r['abastecimiento_ultimo_pct']} %", f"{r['abastecimiento_ultimo_pct'] - r['abastecimiento_en_hito_pct']:+.1f} p.p. desde oct-2025")
    c[1].metric("Críticos sin existencia", r["criticos_en_cero_ultimo"], f"{r['criticos_en_cero_ultimo'] - r['criticos_en_cero_en_hito']:+d} desde oct-2025", delta_color="inverse")
    c[2].metric("Promedio 6 meses antes → últimos 6", f"{r['abastecimiento_antes_pct']} % → {r['abastecimiento_despues_pct']} %")
    fig = go.Figure()
    fig.add_scatter(x=k["periodo"], y=k["pct_abastecimiento"], name="% abastecimiento", line=dict(color=VIOLETA, width=3))
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
