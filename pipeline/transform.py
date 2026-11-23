"""Etapa 2 — Limpieza, unificación y transformación.

Convierte las tres fuentes crudas (`data/raw/`) en tablas limpias (`data/processed/`):

| Tabla | Grano | Origen |
|---|---|---|
| `existencias.csv` | medicamento × mes × centro de distribución | CSV de inventario CSS |
| `medicamentos.csv` | medicamento (código CSS de 9 dígitos) | CSV CSS + código SAFIRO/ATC |
| `equivalencias_codigos.csv` | código tal como aparece en la fuente | CSV CSS |
| `totales_referencia.csv` | medicamento × mes (total nacional publicado) | Cuadros comparativos CSS |
| `fda_escasez.csv` | presentación en escasez (EE. UU.) | openFDA (JSON) |
| `documentos.jsonl` | noticia o informe | Texto (HTML/PDF) |
| `incidencias.csv` | problema de calidad detectado | Todas |

Uso:  python -m pipeline.transform  [--raw RUTA] [--salida RUTA]
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import CENTROS, PROCESSED, RAW
from .lectura import (
    RE_ATC, anio_en_texto, codigo_con_guiones, es_numero, leer_filas, limpiar_texto,
    mes_en_texto, meses_hasta, normalizar_codigo, numero, periodos_de_archivo,
    principio_activo, sin_acentos,
)

log = logging.getLogger("transform")

# Series de totales mensuales publicadas en los cuadros comparativos que se usan como
# referencia (validación cruzada y año 2020, que no tiene detalle por centro).
# archivo: (columna del código, primera columna de valores, primer mes, n.º de meses)
REFERENCIAS = {
    "cuadro-comparativo-de-existencias-de-enero-a-diciembre-ano-2021.csv": (0, 3, "2020-01", 24),
    "cuadro-comparativo-de-medicamentos-dic.-2022.csv": (0, 3, "2022-01", 12),
    "cuadro-comparativo-de-medicamentos-dic.-2023.csv": (1, 4, "2023-01", 12),
    "cuadro-comparativo-de-medicamentos-octubre-2024.csv": (1, 4, "2023-12", 11),
}

# Primer nivel de la clasificación ATC (OMS).
ATC_NIVEL1 = {
    "A": "Tracto alimentario y metabolismo", "B": "Sangre y órganos hematopoyéticos",
    "C": "Sistema cardiovascular", "D": "Dermatológicos", "G": "Sistema genitourinario y hormonas sexuales",
    "H": "Hormonas sistémicas", "J": "Antiinfecciosos sistémicos", "L": "Antineoplásicos e inmunomoduladores",
    "M": "Sistema musculoesquelético", "N": "Sistema nervioso", "P": "Antiparasitarios",
    "R": "Sistema respiratorio", "S": "Órganos de los sentidos", "V": "Varios",
}
# Grupos de tratamiento continuo o de alto impacto si faltan (propuesta para validar
# con la Dirección Nacional de Farmacia). Se evalúan en orden: el prefijo más específico primero.
CATEGORIAS_CRITICAS = [
    ("A10A", "Insulinas"), ("A10B", "Antidiabéticos orales"), ("L01", "Oncológicos"),
    ("L02", "Terapia hormonal oncológica"), ("L04", "Inmunosupresores"),
    ("J05A", "Antivirales (incluye VIH)"), ("B01", "Antitrombóticos"), ("N03", "Antiepilépticos"),
    ("H03", "Tiroides"), ("R03", "Asma y EPOC"), ("C", "Cardiovascular"),
]


@dataclass
class Bloque:
    """Grupo de columnas de un mismo mes: existencias por centro, total y monto."""
    periodo: str | None
    cols: dict = field(default_factory=dict)


class Incidencias:
    def __init__(self):
        self.filas: list[dict] = []

    def add(self, tipo, archivo="", codigo="", periodo="", detalle=""):
        self.filas.append({"tipo": tipo, "archivo": archivo, "codigo": codigo,
                           "periodo": periodo, "detalle": detalle})


# ------------------------------------------------------------------ CSS
def clasificar(nombre: str) -> str | None:
    n = nombre.lower()
    if "insumo" in n:
        return None                      # fuera del alcance: insumos médico-quirúrgicos
    if any(k in n for k in ("compar", "comporativo", "corporativo")):
        return "comparativo"
    return "inventario"


def _separar(filas):
    for i, f in enumerate(filas):
        if f and normalizar_codigo(f[0]):
            return filas[:i], [x for x in filas[i:] if x and normalizar_codigo(x[0])]
    return filas, []


def _textos_encabezado(enc, ncols):
    textos = [""] * ncols
    for fila in enc:
        for j, c in enumerate(fila[:ncols]):
            if c.strip():
                textos[j] = limpiar_texto(f"{textos[j]} {c}")
    return [sin_acentos(t.upper()) for t in textos]


def _bloques_con_encabezado(textos, periodos, anio_archivo):
    meta, bloques, actual = {}, [], None
    for j, t in enumerate(textos):
        if j < 2:
            continue
        centro = next((c for c in CENTROS if c in t), None)
        if centro:
            if actual is None or centro in actual.cols:
                mes, anio = mes_en_texto(t), anio_en_texto(t) or anio_archivo
                per = f"{anio}-{mes:02d}" if mes and anio else (periodos[0] if len(periodos) == 1 else None)
                actual = Bloque(per)
                bloques.append(actual)
            actual.cols[centro] = j
        elif "MONTO" in t and actual:
            actual.cols["MONTO"] = j
        elif "TOTAL" in t and actual:
            actual.cols["TOTAL"] = j
        elif "PRECIO" in t:
            meta["precio"] = j
        elif "TIPO" in t:
            meta["tipo"] = j
    return meta, bloques


def _bloques_sin_encabezado(datos, periodos, nombre):
    con_tipo = sum(1 for f in datos[:100] if len(f) > 2 and f[2].strip() and not es_numero(f[2])) > 50
    meta = {"tipo": 2, "precio": 3} if con_tipo else {"precio": 2}
    inicio = meta["precio"] + 1
    ncols = max((j + 1 for f in datos for j, c in enumerate(f) if c.strip()), default=0)
    n = ncols - inicio
    if n <= 0 or n % 5:
        raise ValueError(f"{nombre}: {n} columnas numéricas, no es múltiplo de 5")
    k = n // 5
    if len(periodos) == k:
        pers = periodos
    elif len(periodos) == 1:
        pers = meses_hasta(periodos[0], k)
    else:
        raise ValueError(f"{nombre}: {k} bloques para {len(periodos)} meses")
    bloques = []
    for b in range(k):
        base = inicio + 5 * b
        # ¿El total va en la 4.ª o en la 5.ª columna del bloque? Se decide por mayoría.
        votos = [0, 0]
        for f in datos:
            v = [numero(f[base + i]) if base + i < len(f) else None for i in range(5)]
            if None in v[:3]:
                continue
            s = sum(v[:3])
            for pos in (0, 1):
                if v[3 + pos] is not None and abs(v[3 + pos] - s) < 0.5:
                    votos[pos] += 1
        pos_total = 3 if votos[0] >= votos[1] else 4
        bloques.append(Bloque(pers[b], {"CDPA": base, "CDDI": base + 1, "CDCH": base + 2,
                                         "TOTAL": base + pos_total, "MONTO": base + (7 - pos_total)}))
    return meta, bloques


def leer_inventario(ruta: Path, inc: Incidencias):
    """Devuelve (registros, info) de un archivo de inventario."""
    filas, info = leer_filas(ruta)
    enc, datos = _separar(filas)
    periodos = periodos_de_archivo(ruta.name)
    if not datos or not periodos:
        inc.add("archivo_no_interpretable", ruta.name, detalle="sin filas de datos o sin período en el nombre")
        return [], info
    ncols = max(len(f) for f in filas)
    textos = _textos_encabezado(enc, ncols)
    if any(c in t for t in textos for c in CENTROS):
        meta, bloques = _bloques_con_encabezado(textos, periodos, anio_en_texto(ruta.name))
        info["encabezado"] = True
    else:
        meta, bloques = _bloques_sin_encabezado(datos, periodos, ruta.name)
        info["encabezado"] = False

    # Las plantillas trimestrales traen bloques vacíos o repetidos: por cada mes del
    # archivo se conserva el bloque con más celdas con valor.
    def llenas(b):
        return sum(1 for f in datos for c in CENTROS
                   if c in b.cols and b.cols[c] < len(f) and (numero(f[b.cols[c]]) or 0) != 0)
    elegidos = {}
    for b in bloques:
        if b.periodo not in periodos:
            continue
        n = llenas(b)
        if n and (b.periodo not in elegidos or n > elegidos[b.periodo][1]):
            elegidos[b.periodo] = (b, n)
    for p in periodos:
        if p not in elegidos:
            inc.add("mes_sin_datos", ruta.name, periodo=p, detalle="el archivo nombra el mes pero no trae valores")
    info["periodos"] = sorted(elegidos)

    def celda(f, j):
        return f[j] if j is not None and j < len(f) else ""

    registros, vistos = [], set()
    for f in datos:
        cod_fuente = limpiar_texto(f[0])
        cod = normalizar_codigo(cod_fuente)
        desc = limpiar_texto(celda(f, 1))
        precio = numero(celda(f, meta.get("precio")))
        tipo = limpiar_texto(celda(f, meta.get("tipo"))) or None
        for per, (b, _) in elegidos.items():
            if (cod, per) in vistos:
                inc.add("codigo_duplicado_en_archivo", ruta.name, cod, per, desc)
                continue
            cant = {c: numero(celda(f, b.cols.get(c))) for c in CENTROS}
            total = numero(celda(f, b.cols.get("TOTAL")))
            monto = numero(celda(f, b.cols.get("MONTO")))
            if all(v is None for v in cant.values()) and total is None:
                continue
            vistos.add((cod, per))
            cant = {c: (v or 0.0) for c, v in cant.items()}
            registros.append({
                "codigo": cod, "codigo_fuente": cod_fuente, "descripcion": desc, "tipo_compra": tipo,
                "periodo": per, "precio_unitario": precio, **cant,
                "total_reportado": total, "monto_reportado": monto, "archivo": ruta.name,
            })
    return registros, info


def leer_comparativo(ruta: Path):
    """Catálogo SAFIRO/ATC y, si el archivo está en REFERENCIAS, la serie de totales."""
    filas, _ = leer_filas(ruta)
    atc, serie = {}, []
    for f in filas:
        if len(f) > 3 and normalizar_codigo(f[1]) and RE_ATC.match(f[2].strip()):
            atc[normalizar_codigo(f[1])] = f[2].strip()
    conf = REFERENCIAS.get(ruta.name)
    if conf:
        col_cod, col_ini, desde, n = conf
        a, m = map(int, desde.split("-"))
        pers = meses_hasta(f"{a + (m - 1 + n - 1) // 12}-{(m - 1 + n - 1) % 12 + 1:02d}", n)
        for f in filas:
            if len(f) <= col_cod or not normalizar_codigo(f[col_cod]):
                continue
            cod = normalizar_codigo(f[col_cod])
            for i, p in enumerate(pers):
                v = numero(f[col_ini + i]) if col_ini + i < len(f) else None
                if v is not None:
                    serie.append({"codigo": cod, "periodo": p, "total_reportado": v, "archivo": ruta.name})
    return atc, serie


def transformar_css(dir_css: Path, inc: Incidencias):
    archivos = sorted(dir_css.glob("*.csv"))
    registros, atc, referencia, lecturas = [], {}, [], []
    for ruta in archivos:
        clase = clasificar(ruta.name)
        if clase is None:
            inc.add("archivo_excluido", ruta.name, detalle="insumos médico-quirúrgicos (fuera del alcance)")
            continue
        try:
            if clase == "inventario":
                regs, info = leer_inventario(ruta, inc)
                registros += regs
                lecturas.append({"archivo": ruta.name, "familia": clase, "filas": len(regs), **info})
            else:
                a, serie = leer_comparativo(ruta)
                atc.update(a)
                referencia += serie
                lecturas.append({"archivo": ruta.name, "familia": clase, "filas": len(serie)})
        except Exception as e:                       # un archivo malo no detiene el pipeline
            inc.add("error_de_lectura", ruta.name, detalle=str(e))
            log.warning("No se pudo leer %s: %s", ruta.name, e)

    df = pd.DataFrame(registros)
    if df.empty:
        raise SystemExit("No se leyó ningún registro de inventario.")

    # Un mismo mes puede venir en dos archivos (p. ej. may–sep 2024 y may–oct 2024):
    # se conserva el del archivo publicado después.
    fin = df.groupby("archivo")["periodo"].max().rename("fin_archivo")
    df = df.join(fin, on="archivo").sort_values(["codigo", "periodo", "fin_archivo", "archivo"])
    dup = df.duplicated(["codigo", "periodo"], keep="last")
    for (cod, per), g in df[df.duplicated(["codigo", "periodo"], keep=False)].groupby(["codigo", "periodo"]):
        if g[list(CENTROS)].nunique().max() > 1:
            inc.add("mes_repetido_con_valores_distintos", ";".join(g["archivo"]), cod, per,
                    "se conserva el archivo más reciente")
    df = df[~dup].drop(columns="fin_archivo")

    # Precio: la CSS publica el precio redondeado (p. ej. 0.03) pero calcula el monto con
    # el precio completo (0.0271…). Cuando hay monto y total, se usa el precio efectivo
    # (monto ÷ total), que reproduce el valor oficial; si no, el precio publicado.
    df = df.sort_values(["codigo", "periodo"])
    df["precio_publicado"] = df["precio_unitario"]
    efectivo = df["monto_reportado"] / df["total_reportado"]
    usar = df["total_reportado"].gt(0) & df["monto_reportado"].gt(0)
    df.loc[usar, "precio_unitario"] = efectivo[usar].round(6)
    dif = usar & df["precio_publicado"].gt(0) & ((efectivo / df["precio_publicado"] - 1).abs() > 0.05)
    for r in df[dif].itertuples():
        inc.add("precio_publicado_redondeado", r.archivo, r.codigo, r.periodo,
                f"publicado {r.precio_publicado} vs efectivo {r.precio_unitario:.4f}")

    # Los archivos de ene–jul 2021 no traen precio: se toma el del mes más cercano del
    # mismo medicamento y se marca como imputado.
    df["precio_imputado"] = df["precio_unitario"].isna() | (df["precio_unitario"] <= 0)
    df.loc[df["precio_imputado"], "precio_unitario"] = None
    df["precio_unitario"] = df.groupby("codigo")["precio_unitario"].transform(lambda s: s.bfill().ffill())

    # Validaciones por fila
    suma = df[list(CENTROS)].sum(axis=1)
    malos = df["total_reportado"].notna() & ((suma - df["total_reportado"]).abs() > 0.5)
    for r in df[malos].itertuples():
        inc.add("total_no_cuadra", r.archivo, r.codigo, r.periodo,
                f"suma centros {suma[r.Index]:,.0f} vs total publicado {r.total_reportado:,.0f}")
    neg = (df[list(CENTROS)] < 0).any(axis=1)
    for r in df[neg].itertuples():
        inc.add("existencia_negativa", r.archivo, r.codigo, r.periodo)
    valor = suma * df["precio_unitario"]
    malm = df["monto_reportado"].notna() & ((valor - df["monto_reportado"]).abs() > (0.01 * valor.abs()).clip(lower=1))
    for r in df[malm].itertuples():
        inc.add("monto_no_cuadra", r.archivo, r.codigo, r.periodo,
                f"cantidad×precio {valor[r.Index]:,.2f} vs monto publicado {r.monto_reportado:,.2f}")
    for cod in df.loc[df["precio_unitario"].isna(), "codigo"].unique():
        inc.add("sin_precio", codigo=cod, detalle="ningún archivo informa precio")

    # Atípicos: total del mes más de 20 veces la mediana de los meses con existencia del
    # mismo medicamento (p. ej. filas corridas en la fuente). No se borran: se marcan.
    df["total_calc"] = suma
    pos = df[df["total_calc"] > 0].groupby("codigo")["total_calc"].agg(["median", "count"])
    df = df.join(pos, on="codigo")
    df["atipico"] = (df["count"] >= 6) & (df["total_calc"] > 20 * df["median"]) & (df["total_calc"] > 1000)
    for r in df[df["atipico"]].itertuples():
        inc.add("cantidad_atipica", r.archivo, r.codigo, r.periodo,
                f"total {r.total_calc:,.0f} vs mediana {r.median:,.0f}")
    df = df.drop(columns=["total_calc", "median", "count"])

    # Tabla larga: una fila por medicamento × mes × centro
    largo = df.melt(id_vars=["codigo", "periodo", "precio_unitario", "precio_imputado", "atipico", "archivo"],
                    value_vars=list(CENTROS), var_name="centro", value_name="cantidad")
    largo["valor"] = (largo["cantidad"] * largo["precio_unitario"]).round(2)
    largo["anio"] = largo["periodo"].str[:4].astype(int)
    largo["mes"] = largo["periodo"].str[5:].astype(int)
    existencias = largo[["periodo", "anio", "mes", "codigo", "centro", "cantidad", "precio_unitario",
                         "valor", "precio_imputado", "atipico", "archivo"]].sort_values(["periodo", "codigo", "centro"])

    # Catálogo de medicamentos
    ult = df.sort_values("periodo").groupby("codigo").last()
    agg = df.groupby("codigo").agg(primer_periodo=("periodo", "min"), ultimo_periodo=("periodo", "max"),
                                   meses_con_dato=("periodo", "nunique"))
    tipo = df.dropna(subset=["tipo_compra"]).sort_values("periodo").groupby("codigo")["tipo_compra"].last()
    med = agg.join(ult[["descripcion", "precio_unitario"]]).join(tipo)
    med["codigo_guiones"] = [codigo_con_guiones(c) for c in med.index]
    med["principio_activo"] = med["descripcion"].map(principio_activo)
    med["atc"] = med.index.map(atc.get)
    med["atc_nivel1"] = med["atc"].str[0]
    med["grupo_terapeutico"] = med["atc_nivel1"].map(ATC_NIVEL1)

    def categoria(a):
        if not isinstance(a, str):
            return None
        return next((n for p, n in CATEGORIAS_CRITICAS if a.startswith(p)), None)
    med["categoria_critica"] = med["atc"].map(categoria)
    med["critico"] = med["categoria_critica"].notna()
    med = med.reset_index().rename(columns={"precio_unitario": "precio_ultimo"})
    med = med[["codigo", "codigo_guiones", "descripcion", "principio_activo", "atc", "atc_nivel1",
               "grupo_terapeutico", "categoria_critica", "critico", "tipo_compra", "precio_ultimo",
               "primer_periodo", "ultimo_periodo", "meses_con_dato"]]
    for cod in med.loc[med["atc"].isna(), "codigo"]:
        inc.add("sin_codigo_atc", codigo=cod, detalle="no aparece en los cuadros comparativos con SAFIRO")

    # Mismo código con descripciones distintas (posible reutilización de código)
    descs = df.assign(base=df["descripcion"].map(principio_activo)).groupby("codigo")["base"].unique()
    for cod, bases in descs.items():
        if len(bases) > 1:
            inc.add("codigo_con_varias_descripciones", codigo=cod, detalle=" | ".join(bases))

    # Equivalencias: cada código tal como aparece en la fuente → código unificado
    eq = (df.groupby("codigo_fuente")
            .agg(codigo=("codigo", "first"), primer_periodo=("periodo", "min"),
                 ultimo_periodo=("periodo", "max"), archivos=("archivo", "nunique"))
            .reset_index())
    eq["formato"] = eq["codigo_fuente"].map(lambda s: "con guiones" if "-" in s else "9 dígitos")

    ref = pd.DataFrame(referencia).drop_duplicates(["codigo", "periodo"], keep="last") if referencia else pd.DataFrame()
    return existencias, med, eq, ref, pd.DataFrame(lecturas)


# --------------------------------------------------------------- openFDA
def transformar_openfda(ruta: Path, inc: Incidencias) -> pd.DataFrame:
    if not ruta.exists():
        inc.add("fuente_ausente", ruta.name)
        return pd.DataFrame()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    res = datos.get("results", datos) if isinstance(datos, dict) else datos

    def fecha(s):
        d = pd.to_datetime(s, format="%m/%d/%Y", errors="coerce")
        return None if pd.isna(d) else d.strftime("%Y-%m-%d")

    def unir(x):
        return "; ".join(x) if isinstance(x, list) else x

    filas = []
    for r in res:
        o = r.get("openfda", {}) or {}
        filas.append({
            "generic_name": r.get("generic_name"),
            "sustancia": unir(o.get("substance_name")) or r.get("generic_name"),
            "status": r.get("status"),
            "availability": r.get("availability"),
            "categoria_terapeutica": unir(r.get("therapeutic_category")),
            "forma": r.get("dosage_form"),
            "presentacion": r.get("presentation"),
            "empresa": r.get("company_name"),
            "motivo": r.get("shortage_reason"),
            "fecha_inicio": fecha(r.get("initial_posting_date")),
            "fecha_actualizacion": fecha(r.get("update_date")),
            "fecha_descontinuacion": fecha(r.get("discontinued_date")),
            "package_ndc": r.get("package_ndc"),
        })
    df = pd.DataFrame(filas)
    sin = df["generic_name"].isna().sum()
    if sin:
        inc.add("openfda_sin_nombre", ruta.name, detalle=f"{sin} registros sin generic_name")
    return df


# ------------------------------------------------------------------ texto
def transformar_texto(dir_txt: Path, inc: Incidencias) -> list[dict]:
    fuentes = dir_txt / "fuentes_texto.csv"
    if not fuentes.exists():
        inc.add("fuente_ausente", "fuentes_texto.csv")
        return []
    docs = []
    with fuentes.open(encoding="utf-8") as fh:
        for f in csv.DictReader(fh):
            id_ = f.get("id")
            texto, origen = "", None
            for ext in ("txt", "pdf"):
                p = dir_txt / f"{id_}.{ext}"
                if p.exists():
                    origen = p.name
                    texto = p.read_text(encoding="utf-8", errors="replace") if ext == "txt" else _texto_pdf(p)
                    break
            texto = limpiar_texto(texto)
            estado = "ok" if len(texto) >= 500 else ("incompleto" if texto else "sin_descarga")
            if estado != "ok":
                inc.add(f"texto_{estado}", origen or id_, detalle=f"{len(texto)} caracteres — {f.get('url', '')}")
            docs.append({**{k: v for k, v in f.items() if k}, "archivo": origen, "texto": texto,
                         "caracteres": len(texto), "estado": estado})
    return docs


def _texto_pdf(ruta: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(ruta)).pages)
    except Exception:
        return ""


# ------------------------------------------------------------------- main
def ejecutar(raw: Path = RAW, salida: Path = PROCESSED) -> dict:
    salida.mkdir(parents=True, exist_ok=True)
    inc = Incidencias()
    existencias, med, eq, ref, lecturas = transformar_css(raw / "css", inc)
    fda = transformar_openfda(raw / "openfda" / "drug_shortages.json", inc)
    docs = transformar_texto(raw / "texto", inc)

    opts = {"index": False, "encoding": "utf-8-sig"}
    existencias.to_csv(salida / "existencias.csv", **opts)
    med.to_csv(salida / "medicamentos.csv", **opts)
    eq.to_csv(salida / "equivalencias_codigos.csv", **opts)
    ref.to_csv(salida / "totales_referencia.csv", **opts)
    fda.to_csv(salida / "fda_escasez.csv", **opts)
    lecturas.to_csv(salida / "lectura_archivos.csv", **opts)
    pd.DataFrame(inc.filas, columns=["tipo", "archivo", "codigo", "periodo", "detalle"]).to_csv(
        salida / "incidencias.csv", **opts)
    with (salida / "documentos.jsonl").open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    resumen = {
        "existencias": len(existencias), "medicamentos": len(med), "periodos": existencias["periodo"].nunique(),
        "desde": existencias["periodo"].min(), "hasta": existencias["periodo"].max(),
        "fda_escasez": len(fda), "documentos": len(docs), "incidencias": len(inc.filas),
    }
    log.info("Listo: %s", resumen)
    return resumen


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", type=Path, default=RAW, help="carpeta de datos crudos (por defecto data/raw)")
    ap.add_argument("--salida", type=Path, default=PROCESSED, help="carpeta de salida (por defecto data/processed)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(ejecutar(a.raw, a.salida), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
