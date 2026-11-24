"""Genera las páginas del reporte Power BI (formato PBIR) y ajusta el modelo: formatos, columnas de la
respuesta (acción por medicamento) y medidas. Es idempotente: se puede correr varias veces."""
import json, re, shutil, sys, uuid
from pathlib import Path

BASE = Path(sys.argv[1])
REP = BASE / "CSS_inventario_medicamentos.Report" / "definition"
SEM = BASE / "CSS_inventario_medicamentos.SemanticModel" / "definition"
VS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
PS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
# Paleta institucional azul/celeste de la Caja de Seguro Social
AZUL, OSCURO, CELESTE = "#0B5394", "#0A2F5C", "#3DA5D9"
ROJO, GRIS, AMBAR, VERDE = "#C0392B", "#7F8C9A", "#E08E0B", "#2E7D5B"
FONDO, BORDE = "#F4F8FB", "#D3E7F6"
ACCIONES = {"1 · Comprar ya": ROJO, "2 · Reforzar compra": AMBAR, "3 · Trasladar": AZUL, "4 · Vigilar": CELESTE, "5 · Sin acción": GRIS}

# ------------------------------------------------------------ modelo: formatos
tm = SEM / "tables" / "existencias.tmdl"
t = tm.read_text(encoding="utf-8")
t = re.sub(r"\n\t\tannotation PBI_FormatHint = .*\n", "\n", t)
formatos = {
    "'% abastecimiento'": "0.0%", "'Abastecimiento oficial'": "0.0%", "'Abastecimiento último mes'": "0.0%",
    "'Variación 12 meses %'": "+0.0%;-0.0%", "'Valor inventario'": "#,0", "'Valor año anterior'": "#,0",
    "'Valor promedio mensual'": "#,0", "'Dinero inmovilizado'": "#,0", "'Valor de traslados'": "#,0",
    "'Valor último mes'": "#,0", "Unidades": "#,0", "Renglones-mes": "#,0", "'Renglones en cero'": "#,0",
    "'Brecha declarada (p.p.)'": "0.0", "'Críticos en cero último mes'": "0",
}
lineas = t.split("\n")
out = []
i = 0
while i < len(lineas):
    l = lineas[i]
    if l is None:
        i += 1
        continue
    out.append(l)
    m = re.match(r"\tmeasure (.+?) = ", l)
    if m and m.group(1) in formatos:
        # quitar formatString previo del bloque si existe
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("\t\t"):
            if lineas[j].strip().startswith("formatString:"):
                lineas[j] = None
            j += 1
        out.append(f"\t\tformatString: {formatos[m.group(1)]}")
    i += 1
tm.write_text("\n".join(x for x in out if x is not None), encoding="utf-8", newline="\r\n")

rel = SEM / "relationships.tmdl"
r = rel.read_text(encoding="utf-8")
r = r.replace("\tfromColumn: p6_fantasmas.codigo\n", "\tcrossFilteringBehavior: bothDirections\n\tfromColumn: p6_fantasmas.codigo\n", 1) \
    if "crossFilteringBehavior: bothDirections\n\tfromColumn: p6_fantasmas.codigo" not in r else r
rel.write_text(r, encoding="utf-8", newline="\r\n")


# ------------------------------------------------------------ modelo: respuesta a la pregunta gerencial
# Columnas calculadas en riesgo_medicamentos: la acción de cada medicamento y su grupo de pacientes.
COLUMNAS = {
    "accion": ('SWITCH ( TRUE (), riesgo_medicamentos[nivel_riesgo] = "alto" && riesgo_medicamentos[existencia_total] <= 0, "1 · Comprar ya", '
               'riesgo_medicamentos[nivel_riesgo] = "alto", "2 · Reforzar compra", '
               'NOT ISEMPTY ( FILTER ( ALL ( redistribucion[codigo] ), redistribucion[codigo] = riesgo_medicamentos[codigo] ) ), "3 · Trasladar", '
               'riesgo_medicamentos[nivel_riesgo] = "medio", "4 · Vigilar", "5 · Sin acción" )'),
    "grupo_paciente": ('IF ( ISBLANK ( riesgo_medicamentos[categoria_critica] ) || riesgo_medicamentos[categoria_critica] = "", '
                       '"No crítico", riesgo_medicamentos[categoria_critica] )'),
}
rt = SEM / "tables" / "riesgo_medicamentos.tmdl"
t = rt.read_text(encoding="utf-8")
for nombre, expr in COLUMNAS.items():
    if f"\tcolumn {nombre} =" not in t:
        bloque = (f"\tcolumn {nombre} = {expr}\n\t\tdataType: string\n\t\tlineageTag: {uuid.uuid4()}\n"
                  f"\t\tsummarizeBy: none\n\n\t\tannotation SummarizationSetBy = Automatic\n\n")
        t = t.replace("\tpartition riesgo_medicamentos = m", bloque + "\tpartition riesgo_medicamentos = m", 1)
rt.write_text(t, encoding="utf-8", newline="\r\n")

MEDIDAS = {
    "'Medicamentos en riesgo'": "COUNTROWS ( riesgo_medicamentos )",
    "'Comprar ya'": 'CALCULATE ( [Críticos en riesgo alto], riesgo_medicamentos[accion] = "1 · Comprar ya" )',
    "'Reforzar compra'": 'CALCULATE ( [Críticos en riesgo alto], riesgo_medicamentos[accion] = "2 · Reforzar compra" )',
    "'Traslados de críticos'": "CALCULATE ( COUNTROWS ( redistribucion ), redistribucion[critico] = TRUE () )",
}
t = tm.read_text(encoding="utf-8")
nuevas = ""
for nombre, expr in MEDIDAS.items():
    if f"\tmeasure {nombre} =" not in t:
        nuevas += f"\tmeasure {nombre} = {expr}\n\t\tformatString: 0\n\t\tlineageTag: {uuid.uuid4()}\n\n"
if nuevas:
    t = t.replace("\tcolumn periodo\n", nuevas + "\tcolumn periodo\n", 1)
    tm.write_text(t, encoding="utf-8", newline="\r\n")

# ------------------------------------------------------------ ayudas PBIR
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}

def s(txt):
    return lit("'" + txt.replace("'", "''") + "'")

def color(c):
    return {"solid": {"color": s(c)}}

def M(ent, prop):
    return ({"Measure": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}, f"{ent}.{prop}", prop)

def C(ent, prop):
    return ({"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}, f"{ent}.{prop}", prop)

def SUM(ent, prop):
    col = {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}
    return ({"Aggregation": {"Expression": col, "Function": 0}}, f"Sum({ent}.{prop})", prop)

def proj(f):
    return {"field": f[0], "queryRef": f[1], "nativeQueryRef": f[2]}

def titulo(txt, tam="14"):
    return {"title": [{"properties": {"show": lit("true"), "text": s(txt), "fontColor": color(OSCURO),
                                      "fontSize": lit(f"{tam}D"), "bold": lit("true")}}],
            "background": [{"properties": {"show": lit("true"), "color": color("#FFFFFF")}}],
            "border": [{"properties": {"show": lit("true"), "color": color(BORDE), "radius": lit("8D")}}]}

def visual(tipo, x, y, w, h, roles=None, title=None, objects=None, sort=None, filters=None, z=0):
    v = {"$schema": VS, "name": uuid.uuid4().hex[:20],
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
         "visual": {"visualType": tipo, "drillFilterOtherVisuals": True}}
    if roles:
        q = {"queryState": {k: {"projections": [proj(f) for f in fs]} for k, fs in roles.items()}}
        if sort:
            q["sortDefinition"] = {"sort": [{"field": sort[0][0], "direction": sort[1]}], "isDefaultSort": False}
        v["visual"]["query"] = q
    if objects:
        v["visual"]["objects"] = objects
    if title:
        v["visual"]["visualContainerObjects"] = titulo(title)
    if filters:
        v["filterConfig"] = {"filters": filters}
    return v

def texto(x, y, w, h, parrafos, z=0):
    ps = []
    for p in parrafos:
        runs = []
        for txt, estilo in p:
            runs.append({"value": txt, "textStyle": estilo})
        ps.append({"textRuns": runs})
    return {"$schema": VS, "name": uuid.uuid4().hex[:20],
            "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
            "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": ps}}]},
                       "visualContainerObjects": {"background": [{"properties": {"show": lit("false")}}]}}}

def encabezado(pregunta, titular, decision, ancho=1840):
    return texto(40, 20, ancho, 150, [
        [(pregunta, {"fontSize": "14pt", "color": GRIS})],
        [(titular, {"fontSize": "30pt", "fontWeight": "bold", "color": OSCURO})],
        [("Decisión: ", {"fontSize": "14pt", "fontWeight": "bold", "color": AZUL}), (decision, {"fontSize": "14pt", "color": "#14212E"})],
    ])

def pie(fuente):
    return texto(40, 1030, 1840, 40, [[(f"Fuente: {fuente}. Datos abiertos de la CSS procesados por el pipeline css-pharma-supply-analytics.",
                                        {"fontSize": "10pt", "color": GRIS})]])

def tarjeta(x, y, medida, etiqueta, ent="existencias", w=430, h=150, c=AZUL):
    return visual("card", x, y, w, h, {"Values": [M(ent, medida)]}, title=etiqueta,
                  objects={"labels": [{"properties": {"color": color(c), "fontSize": lit("34D"), "labelDisplayUnits": lit("1D")}}],
                           "categoryLabels": [{"properties": {"show": lit("false")}}]})

def filtro_in(nombre, ent, prop, valores):
    alias = ent[0]
    return {"name": nombre, "field": C(ent, prop)[0], "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": alias, "Entity": ent, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}}],
                                                       "Values": [[{"Literal": {"Value": v}}] for v in valores]}}}]}}

def filtro_mayor(nombre, ent, prop, valor):
    alias = ent[0]
    return {"name": nombre, "field": C(ent, prop)[0], "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": alias, "Entity": ent, "Type": 0}],
                       "Where": [{"Condition": {"Comparison": {"ComparisonKind": 1,
                                                               "Left": {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}},
                                                               "Right": {"Literal": {"Value": f"{valor}D"}}}}}]}}

def puntos(c):
    return {"dataPoint": [{"properties": {"fill": color(c)}}]}


def segmentador(x, y, w, h, campo, titulo_txt, modo="Dropdown"):
    return visual("slicer", x, y, w, h, {"Values": [campo]}, title=titulo_txt,
                  objects={"data": [{"properties": {"mode": s(modo)}}]})

def anio(x=1500, y=30, w=380, h=110):
    """Segmentador de años (filtra las series mensuales relacionadas con Calendario)."""
    return segmentador(x, y, w, h, C("Calendario", "Año"), "Filtrar por año")

def colores_serie(ent, prop, mapa):
    col = {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}
    return {"dataPoint": [{"properties": {"fill": color(c)},
                           "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col,
                                                                             "Right": {"Literal": {"Value": "'" + v + "'"}}}}}]}}
                          for v, c in mapa.items()]}

# ------------------------------------------------------------ páginas
paginas = []

def pagina(nombre, visuales):
    pid = uuid.uuid4().hex[:20]
    paginas.append((pid, nombre, visuales))

pagina("Resumen", [
    texto(40, 20, 1420, 130, [
        [("Sistema de Información Gerencial · Inventario de medicamentos de la Caja de Seguro Social", {"fontSize": "14pt", "color": GRIS})],
        [("¿Qué medicamentos están en riesgo y cómo redistribuirlos?", {"fontSize": "30pt", "fontWeight": "bold", "color": OSCURO})]]),
    anio(),
    tarjeta(40, 170, "Abastecimiento último mes", "Abastecimiento de los almacenes (último mes)"),
    tarjeta(500, 170, "Críticos en cero último mes", "Medicamentos críticos sin existencia", c=ROJO),
    tarjeta(960, 170, "En riesgo alto", "Medicamentos en riesgo alto", c=ROJO),
    tarjeta(1420, 170, "Valor último mes", "Valor del inventario (B/., último mes)", w=460),
    visual("lineChart", 40, 350, 1100, 650, {"Category": [C("kpi_mensual", "periodo")], "Y": [M("existencias", "Abastecimiento oficial")]},
           title="Abastecimiento mensual de los almacenes, 2021–2026", objects=puntos(AZUL), sort=(C("kpi_mensual", "periodo"), "Ascending")),
    texto(1170, 350, 710, 650, [
        [("Seis hallazgos", {"fontSize": "18pt", "fontWeight": "bold", "color": OSCURO})],
        [("1 · El valor del inventario cayó 64.3 % al iniciar 2025.", {"fontSize": "13pt"})],
        [("2 · Se anuncian 90–96 % de abastecimiento; los datos muestran 78.8–86.3 %.", {"fontSize": "13pt"})],
        [("3 · Asma/EPOC, oncológicos y VIH pasan más meses sin existencia.", {"fontSize": "13pt"})],
        [("4 · Panamá (CDPA) concentra 80.1 % del inventario; el interior se queda en cero.", {"fontSize": "13pt"})],
        [("5 · Desde la Comisión (oct-2025) el abastecimiento subió de 78.8 % a 86.3 %.", {"fontSize": "13pt"})],
        [("6 · 23 medicamentos publicados llevan 12 meses en cero.", {"fontSize": "13pt"})],
        [("Respuesta: 50 críticos en riesgo alto se compran; 143 traslados evitan nuevos quiebres (página La respuesta).", {"fontSize": "13pt", "fontWeight": "bold", "color": AZUL})],
        [("Titulares redactados por IA generativa (Gemini) a partir de las cifras calculadas.", {"fontSize": "10pt", "color": GRIS})]]),
    pie("Dirección Nacional de Logística de la CSS, openFDA y prensa nacional"),
])

pagina("La respuesta", [
    texto(40, 20, 1840, 150, [
        [("Respuesta a la pregunta gerencial · ¿Qué medicamentos están en riesgo de desabastecimiento y cómo redistribuir el inventario?", {"fontSize": "14pt", "color": GRIS})],
        [("50 críticos en riesgo alto se compran; 143 traslados evitan nuevos quiebres", {"fontSize": "30pt", "fontWeight": "bold", "color": OSCURO})],
        [("Respuesta: ", {"fontSize": "14pt", "fontWeight": "bold", "color": AZUL}),
         ("19 críticos no tienen existencia en ningún almacén y 31 tienen menos de un mes sin sobrante en otro centro: se compran. "
          "Los traslados redistribuyen lo que sí sobra (recibe < 1 mes, cede > 4 meses, objetivo 2 meses).", {"fontSize": "14pt", "color": "#14212E"})],
    ]),
    tarjeta(40, 180, "Críticos en riesgo alto", "Críticos en riesgo alto", w=430, h=150),
    tarjeta(500, 180, "Comprar ya", "Comprar ya: sin existencia en ningún almacén", w=430, h=150, c=ROJO),
    tarjeta(960, 180, "Reforzar compra", "Reforzar compra: menos de 1 mes", w=430, h=150, c=AMBAR),
    tarjeta(1420, 180, "Traslados sugeridos", "Trasladar: órdenes entre centros", w=460, h=150),
    segmentador(40, 350, 440, 100, C("riesgo_medicamentos", "grupo_paciente"), "Grupo de pacientes"),
    segmentador(500, 350, 440, 100, C("riesgo_medicamentos", "accion"), "Acción"),
    visual("barChart", 40, 470, 900, 540,
           {"Category": [C("riesgo_medicamentos", "grupo_paciente")], "Y": [M("existencias", "Medicamentos en riesgo")],
            "Series": [C("riesgo_medicamentos", "accion")]},
           title="Qué medicamentos: críticos en riesgo alto por grupo y acción",
           objects=colores_serie("riesgo_medicamentos", "accion", ACCIONES),
           sort=(M("existencias", "Medicamentos en riesgo"), "Descending"),
           filters=[filtro_in("fAltoR", "riesgo_medicamentos", "nivel_riesgo", ["'alto'"]),
                    filtro_in("fCritR", "riesgo_medicamentos", "critico", ["true"])]),
    visual("tableEx", 970, 350, 910, 410,
           {"Values": [C("riesgo_medicamentos", "accion"), C("riesgo_medicamentos", "descripcion"), C("riesgo_medicamentos", "grupo_paciente"),
                       C("riesgo_medicamentos", "existencia_CDPA"), C("riesgo_medicamentos", "existencia_CDDI"), C("riesgo_medicamentos", "existencia_CDCH"),
                       C("riesgo_medicamentos", "cobertura_meses"), C("riesgo_medicamentos", "escasez_eeuu")]},
           title="Lista de compra y refuerzo: medicamentos en riesgo alto (existencia por centro)",
           sort=(C("riesgo_medicamentos", "accion"), "Ascending"),
           filters=[filtro_in("fAltoT", "riesgo_medicamentos", "nivel_riesgo", ["'alto'"])]),
    visual("tableEx", 970, 780, 910, 230,
           {"Values": [C("redistribucion", "desde"), C("redistribucion", "hacia"), M("existencias", "Traslados sugeridos"),
                       M("existencias", "Traslados de críticos"), M("existencias", "Valor de traslados")]},
           title="Cómo redistribuir: traslados por ruta (detalle en la página 4)",
           sort=(M("existencias", "Valor de traslados"), "Descending")),
    pie("Riesgo y redistribución calculados por el pipeline (puntaje 0–100 y regla de traslado, docs/kpi.md)"),
])

pagina("1 · El inventario en 2025", [
    encabezado("P1 · ¿Qué pasó con el inventario de la CSS en 2025?",
               "El valor del inventario cayó 64.3 % al iniciar 2025",
               "definir si el nuevo nivel de inventario es una política de inventario ajustado o un riesgo a corregir.", ancho=1420),
    anio(),
    visual("lineChart", 40, 190, 1240, 520, {"Category": [C("p1_serie", "periodo")], "Y": [SUM("p1_serie", "valor"), SUM("p1_serie", "valor_canasta")]},
           title="Valor del inventario (B/.): total y canasta fija de 480 medicamentos", sort=(C("p1_serie", "periodo"), "Ascending")),
    visual("clusteredColumnChart", 1310, 190, 570, 520, {"Category": [C("Calendario", "Año")], "Y": [M("existencias", "Valor promedio mensual")]},
           title="Valor promedio mensual por año (B/.)", objects=puntos(AZUL), sort=(C("Calendario", "Año"), "Ascending")),
    tarjeta(40, 740, "Dinero inmovilizado", "Apoyo · Dinero inmovilizado (B/., > 12 meses de cobertura)", w=460, h=270, c=AMBAR),
    visual("tableEx", 530, 740, 1350, 270, {"Values": [C("riesgo_medicamentos", "descripcion"), C("riesgo_medicamentos", "cobertura_meses"),
                                                       C("riesgo_medicamentos", "valor_existencia")]},
           title="Medicamentos con más de 12 meses de cobertura", sort=(C("riesgo_medicamentos", "valor_existencia"), "Descending"),
           filters=[filtro_mayor("fCob12", "riesgo_medicamentos", "cobertura_meses", 12)]),
    pie("Inventario mensual de la CSS 2021–2026 (misma canasta de medicamentos, precios estables)"),
])

pagina("2 · ¿90 % de abastecimiento?", [
    encabezado("P2 · ¿Es real el “90 % de abastecimiento” que anuncia la CSS?",
               "Se anuncian 90–96 %; los datos muestran 78.8–86.3 %",
               "acordar un indicador único y público de abastecimiento para rendir cuentas.", ancho=1420),
    anio(),
    visual("lineChart", 40, 190, 1300, 520, {"Category": [C("kpi_mensual", "periodo")], "Y": [M("existencias", "Abastecimiento oficial")]},
           title="Abastecimiento según los datos de la CSS (almacenes centrales)", objects=puntos(AZUL), sort=(C("kpi_mensual", "periodo"), "Ascending")),
    tarjeta(1370, 190, "Brecha declarada (p.p.)", "Brecha promedio: declarado − datos (puntos porcentuales)", w=510, h=250, c=ROJO),
    texto(1370, 460, 510, 250, [[("Cautela", {"fontSize": "14pt", "fontWeight": "bold", "color": AMBAR})],
                                [("Los datos miden existencias en los 3 almacenes centrales; la CSS suele medir disponibilidad en farmacias. "
                                  "La brecha no desmiente la cifra oficial, pero exige un indicador común.", {"fontSize": "12pt"})]]),
    visual("tableEx", 40, 740, 1840, 270, {"Values": [C("p2_declaraciones", "fuente"), C("p2_declaraciones", "fecha"), C("p2_declaraciones", "pct_declarado"),
                                                      C("p2_declaraciones", "pct_datos_mismo_mes"), C("p2_declaraciones", "brecha_pp"), C("p2_declaraciones", "titulo")]},
           title="Declaraciones en prensa leídas por IA (Gemini)"),
    pie("Inventario CSS; noticias de La Estrella, Telemetro, TVN y Panamá América analizadas con Gemini"),
])

pagina("3 · Quiénes pagan", [
    encabezado("P3 · ¿Quiénes pagan el desabastecimiento?",
               "Asma/EPOC, oncológicos y VIH pasan más meses sin existencia",
               "priorizar compras y stock de seguridad por grupo de pacientes, no por renglón."),
    visual("clusteredBarChart", 40, 190, 820, 820, {"Category": [C("p3_grupos", "grupo")], "Y": [SUM("p3_grupos", "pct_meses_en_cero")]},
           title="% de meses sin existencia, últimos 12 meses", objects=puntos(ROJO), sort=(SUM("p3_grupos", "pct_meses_en_cero"), "Descending")),
    visual("slicer", 890, 190, 990, 110, {"Values": [C("riesgo_medicamentos", "categoria_critica")]}, title="Grupo de pacientes",
           objects={"data": [{"properties": {"mode": s("Dropdown")}}]}),
    visual("tableEx", 890, 320, 990, 690, {"Values": [C("riesgo_medicamentos", "descripcion"), C("riesgo_medicamentos", "categoria_critica"),
                                                      C("riesgo_medicamentos", "existencia_total"), C("riesgo_medicamentos", "cobertura_meses"),
                                                      C("riesgo_medicamentos", "puntaje_riesgo"), C("riesgo_medicamentos", "escasez_eeuu")]},
           title="Medicamentos críticos en riesgo alto (escasez_eeuu = también falta en EE. UU., openFDA)",
           sort=(C("riesgo_medicamentos", "puntaje_riesgo"), "Descending"),
           filters=[filtro_in("fAlto", "riesgo_medicamentos", "nivel_riesgo", ["'alto'"]),
                    filtro_in("fCrit", "riesgo_medicamentos", "critico", ["true"])]),
    pie("Inventario CSS (últimos 12 meses), clasificación ATC, openFDA Drug Shortages"),
])

pagina("4 · El interior", [
    encabezado("P4 · ¿El interior del país está peor abastecido?",
               "Panamá concentra 80.1 % del inventario; el interior se queda en cero",
               "ejecutar los traslados sugeridos entre centros antes de comprar y fijar un reparto mínimo para el interior."),
    visual("donutChart", 40, 190, 560, 420, {"Category": [C("p4_centros", "nombre")], "Y": [SUM("p4_centros", "participacion_valor_pct")]},
           title="Participación en el valor del inventario (%)"),
    visual("clusteredColumnChart", 630, 190, 640, 420, {"Category": [C("p4_centros", "nombre")], "Y": [SUM("p4_centros", "pct_en_cero_con_stock_en_otro")]},
           title="% de renglones en cero aunque otro centro sí tiene", objects=puntos(ROJO)),
    tarjeta(1300, 190, "Traslados sugeridos", "Traslados sugeridos", w=580, h=200),
    tarjeta(1300, 410, "Valor de traslados", "Valor de los traslados (B/.)", w=580, h=200),
    visual("slicer", 40, 640, 400, 175, {"Values": [C("redistribucion", "hacia")]}, title="Centro que recibe"),
    segmentador(40, 835, 400, 175, C("medicamentos", "categoria_critica"), "Grupo de pacientes"),
    visual("tableEx", 470, 640, 1410, 370, {"Values": [C("redistribucion", "descripcion"), C("redistribucion", "desde"), C("redistribucion", "hacia"),
                                                       C("redistribucion", "cantidad"), C("redistribucion", "valor"), C("redistribucion", "critico")]},
           title="Órdenes de traslado sugeridas (recibe < 1 mes de cobertura, cede > 4 meses, objetivo 2 meses)",
           sort=(C("redistribucion", "valor"), "Descending")),
    pie("Inventario CSS por centro de distribución (CDPA Panamá, CDDI Divisa, CDCH Chiriquí)"),
])

pagina("5 · La Comisión", [
    encabezado("P5 · ¿Funcionó la Comisión de Desabastecimiento Crítico?",
               "Desde oct-2025 el abastecimiento subió de 78.8 % a 86.3 %",
               "evaluar mantener y ampliar la compra conjunta MINSA–CSS (relación temporal, no prueba de causa).", ancho=1420),
    anio(),
    visual("lineClusteredColumnComboChart", 40, 190, 1300, 820,
           {"Category": [C("kpi_mensual", "periodo")], "Y": [SUM("kpi_mensual", "criticos_en_cero")], "Y2": [M("existencias", "Abastecimiento oficial")]},
           title="Abastecimiento (línea) y medicamentos críticos en cero (columnas). La Comisión se instaló en 2025-10",
           objects=puntos(ROJO), sort=(C("kpi_mensual", "periodo"), "Ascending")),
    tarjeta(1370, 190, "Abastecimiento último mes", "Abastecimiento hoy", w=510, h=180),
    tarjeta(1370, 390, "Críticos en cero último mes", "Críticos sin existencia hoy (eran 31 en oct-2025)", w=510, h=180, c=ROJO),
    visual("tableEx", 1370, 590, 510, 420, {"Values": [C("p5_eventos", "fecha"), C("p5_eventos", "fuente"), C("p5_eventos", "titulo")]},
           title="Línea de tiempo (noticias leídas por IA)", sort=(C("p5_eventos", "fecha"), "Descending")),
    pie("Inventario CSS; noticias analizadas con Gemini"),
])

pagina("6 · Fantasmas", [
    encabezado("P6 · ¿Cuáles son los medicamentos “fantasma”?",
               "23 medicamentos publicados llevan 12 meses en cero",
               "reactivar su compra, buscar un sustituto o depurar el catálogo (5 son críticos).", ancho=1420),
    segmentador(1500, 30, 380, 110, C("p6_fantasmas", "categoria_critica"), "Grupo de pacientes"),
    visual("tableEx", 40, 190, 1000, 820, {"Values": [C("p6_fantasmas", "descripcion"), C("p6_fantasmas", "categoria_critica"),
                                                      C("p6_fantasmas", "ultimo_mes_con_existencia"), C("p6_fantasmas", "precio_ultimo")]},
           title="Medicamentos fantasma (clic en uno para ver su historia)"),
    visual("lineChart", 1070, 190, 810, 820,
           {"Category": [C("existencias", "periodo")], "Y": [M("existencias", "Unidades")], "Series": [C("Centro", "Nombre")]},
           title="Existencia mensual por centro del medicamento seleccionado", sort=(C("existencias", "periodo"), "Ascending")),
    pie("Inventario CSS: renglones publicados en el último corte con 12 meses consecutivos en cero"),
])

# ------------------------------------------------------------ escribir
pdir = REP / "pages"
import time
if pdir.exists():
    shutil.move(str(pdir), str(BASE / f"_respaldo_paginas_{int(time.time())}"))
pdir.mkdir()
for pid, nombre, vis in paginas:
    d = pdir / pid
    (d / "visuals").mkdir(parents=True)
    (d / "page.json").write_text(json.dumps({"$schema": PS, "name": pid, "displayName": nombre, "displayOption": "FitToPage",
                                             "height": 1080, "width": 1920,
                                             "objects": {"background": [{"properties": {"color": color(FONDO), "transparency": lit("0D")}}]}},
                                            ensure_ascii=False, indent=2), encoding="utf-8")
    for v in vis:
        vd = d / "visuals" / v["name"]
        vd.mkdir()
        (vd / "visual.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
(pdir / "pages.json").write_text(json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
                                             "pageOrder": [p[0] for p in paginas], "activePageName": paginas[0][0]}, indent=2), encoding="utf-8")
print("páginas:", len(paginas), "visuales:", sum(len(p[2]) for p in paginas))
