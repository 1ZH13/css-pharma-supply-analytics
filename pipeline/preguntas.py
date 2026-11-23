"""Las 6 preguntas del proyecto: tablas y cifras clave para el dashboard y el documento.

| # | Pregunta | Tabla(s) |
|---|---|---|
| P1 | ¿Qué pasó con el inventario de la CSS en 2025? | p1_serie.csv |
| P2 | ¿Es real el "90 % de abastecimiento" que anuncia la CSS? | p2_declaraciones.csv |
| P3 | ¿Quiénes pagan el desabastecimiento? | p3_grupos.csv |
| P4 | ¿El interior del país está peor abastecido? | p4_centros.csv, p4_rutas.csv |
| P5 | ¿Funcionó la Comisión de Desabastecimiento Crítico? | p5_eventos.csv |
| P6 | ¿Cuáles son los medicamentos "fantasma"? | p6_fantasmas.csv |

Todas las cifras clave quedan en `preguntas_resumen.json` (entrada de la redacción con IA
y de las tarjetas del dashboard). Se excluyen las filas `atipico`.

Uso:  python -m pipeline.preguntas  [--datos RUTA]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CENTROS, PROCESSED

VENTANA = 12
COMISION = "2025-10"            # instalación de la Comisión para la Evaluación del Desabastecimiento Crítico
CORTE_P1 = ("2024-10", "2025-01")
NO_CRITICO = "No crítico"


def _leer(datos: Path, nombre: str) -> pd.DataFrame:
    p = datos / nombre
    return pd.read_csv(p, dtype={"codigo": str}) if p.exists() and p.stat().st_size > 5 else pd.DataFrame()


def _jsonl(datos: Path, nombre: str) -> list[dict]:
    p = datos / nombre
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def _r(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


# ------------------------------------------------------------------- P1
def p1(tot: pd.DataFrame, riesgo: pd.DataFrame):
    periodos = sorted(tot["periodo"].unique())
    # Canasta fija: medicamentos presentes en al menos el 90 % de los meses
    presencia = tot.groupby("codigo")["periodo"].nunique()
    canasta = presencia[presencia >= 0.9 * len(periodos)].index
    s = tot.groupby("periodo").agg(valor=("valor", "sum"), cantidad=("cantidad", "sum")).join(
        tot[tot["codigo"].isin(canasta)].groupby("periodo").agg(valor_canasta=("valor", "sum"),
                                                               cantidad_canasta=("cantidad", "sum")))
    s = s.reset_index()
    s["anio"] = s["periodo"].str[:4].astype(int)

    a, b = CORTE_P1
    ca = tot[tot["periodo"] == a].set_index("codigo")
    cb = tot[tot["periodo"] == b].set_index("codigo")
    comunes = ca.index.intersection(cb.index)
    precio = (cb.loc[comunes, "precio"] / ca.loc[comunes, "precio"]).replace([np.inf, -np.inf], np.nan).dropna()
    anual = s.groupby("anio")["valor"].mean()

    # Dinero inmovilizado (apoyo): valor de lo que tiene más de 12 meses de cobertura
    inmov = riesgo[riesgo["cobertura_meses"] > 12] if len(riesgo) else riesgo
    res = {
        "corte": f"{a} → {b}", "medicamentos_comparados": int(len(comunes)),
        "cambio_cantidad_pct": _r((cb.loc[comunes, "cantidad"].sum() / ca.loc[comunes, "cantidad"].sum() - 1) * 100),
        "cambio_valor_pct": _r((cb.loc[comunes, "valor"].sum() / ca.loc[comunes, "valor"].sum() - 1) * 100),
        "cambio_precio_mediano": _r(precio.median(), 2),
        "valor_mensual_promedio_M": {str(k): _r(v / 1e6) for k, v in anual.items()},
        "valor_ultimo_mes_M": _r(s["valor"].iloc[-1] / 1e6),
        "canasta_fija_medicamentos": int(len(canasta)),
        "inmovilizado_mas_12_meses_M": _r(inmov["valor_existencia"].sum() / 1e6, 2) if len(inmov) else None,
        "inmovilizado_medicamentos": int(len(inmov)),
        "inmovilizado_pct_del_valor": _r(inmov["valor_existencia"].sum() / s["valor"].iloc[-1] * 100) if len(inmov) else None,
    }
    return s, res


# ------------------------------------------------------------------- P2
def p2(kpi: pd.DataFrame, ia: list[dict]):
    serie = kpi.set_index("periodo")["pct_abastecimiento"]
    filas = []
    for d in ia:
        pct = d.get("nivel_abastecimiento_pct")
        if pct is None:
            continue
        fecha = (d.get("fecha_evento") or d.get("fecha_publicada") or "")[:7]
        dato = serie.get(fecha) if len(fecha) == 7 else None
        filas.append({"documento": d.get("id"), "fuente": d.get("fuente"), "titulo": d.get("titulo"), "url": d.get("url"),
                      "fecha": fecha or None, "pct_declarado": pct, "pct_datos_mismo_mes": dato,
                      "brecha_pp": _r(pct - dato) if dato is not None else None, "resumen_ia": d.get("resumen")})
    t = pd.DataFrame(filas)
    ult12 = serie.tail(VENTANA)
    res = {
        "declaraciones": int(len(t)),
        "pct_declarado_min": _r(t["pct_declarado"].min()) if len(t) else None,
        "pct_declarado_max": _r(t["pct_declarado"].max()) if len(t) else None,
        "pct_datos_12m_min": _r(ult12.min()), "pct_datos_12m_max": _r(ult12.max()),
        "pct_datos_ultimo": _r(serie.iloc[-1]),
        "brecha_promedio_pp": _r(t["brecha_pp"].mean()) if len(t) and t["brecha_pp"].notna().any() else None,
        "nota": "Los datos miden existencias en los 3 almacenes centrales; la CSS suele medir disponibilidad en farmacias.",
    }
    return t, res


# ------------------------------------------------------------------- P3
def p3(tot: pd.DataFrame, med: pd.DataFrame, riesgo: pd.DataFrame, fda: pd.DataFrame):
    ult = sorted(tot["periodo"].unique())[-VENTANA:]
    x = tot[tot["periodo"].isin(ult)].merge(med[["codigo", "categoria_critica"]], on="codigo", how="left")
    x["grupo"] = x["categoria_critica"].fillna(NO_CRITICO)
    x["cero"] = x["cantidad"] <= 0
    g = x.groupby("grupo").agg(pct_meses_en_cero=("cero", "mean"), medicamentos=("codigo", "nunique"))
    g["pct_meses_en_cero"] = (g["pct_meses_en_cero"] * 100).round(1)
    if len(riesgo):
        rr = riesgo.assign(grupo=riesgo["categoria_critica"].fillna(NO_CRITICO))
        g = g.join(rr[rr["nivel_riesgo"] == "alto"].groupby("grupo").size().rename("en_riesgo_alto"))
        g = g.join(rr[rr["existencia_total"] <= 0].groupby("grupo").size().rename("sin_existencia_hoy"))
    if len(fda):
        f = fda.merge(med[["codigo", "categoria_critica"]], on="codigo", how="left")
        f["grupo"] = f["categoria_critica"].fillna(NO_CRITICO)
        g = g.join(f[f["escasez_eeuu_vigente"].astype(bool)].groupby("grupo")["codigo"].nunique().rename("escasez_eeuu"))
    g = g.fillna(0).reset_index().sort_values("pct_meses_en_cero", ascending=False)
    for c in ("en_riesgo_alto", "sin_existencia_hoy", "escasez_eeuu"):
        if c in g:
            g[c] = g[c].astype(int)
    base = float(g.loc[g["grupo"] == NO_CRITICO, "pct_meses_en_cero"].iloc[0]) if (g["grupo"] == NO_CRITICO).any() else None
    criticos = g[g["grupo"] != NO_CRITICO]
    res = {
        "ventana": f"{ult[0]} a {ult[-1]}", "pct_no_criticos": base,
        "grupos_peor_que_no_criticos": criticos[criticos["pct_meses_en_cero"] > (base or 0)]["grupo"].tolist(),
        "top3": criticos.head(3)[["grupo", "pct_meses_en_cero"]].to_dict("records"),
        "mejor": criticos.tail(1)[["grupo", "pct_meses_en_cero"]].to_dict("records"),
        "criticos_con_escasez_eeuu": int(criticos["escasez_eeuu"].sum()) if "escasez_eeuu" in criticos else None,
    }
    return g, res


# ------------------------------------------------------------------- P4
def p4(ex: pd.DataFrame, red: pd.DataFrame):
    ult = sorted(ex["periodo"].unique())[-VENTANA:]
    x = ex[ex["periodo"].isin(ult)].copy()
    x["total_pais"] = x.groupby(["periodo", "codigo"])["cantidad"].transform("sum")
    g = x.groupby("centro").agg(valor=("valor", "sum"), filas=("codigo", "size"),
                                en_cero=("cantidad", lambda s: int((s <= 0).sum())))
    g["en_cero_con_stock_en_otro"] = x[(x["cantidad"] <= 0) & (x["total_pais"] > 0)].groupby("centro").size()
    g = g.fillna(0)
    g["participacion_valor_pct"] = (g["valor"] / g["valor"].sum() * 100).round(1)
    g["pct_en_cero"] = (g["en_cero"] / g["filas"] * 100).round(1)
    g["pct_en_cero_con_stock_en_otro"] = (g["en_cero_con_stock_en_otro"] / g["filas"] * 100).round(1)
    g["nombre"] = g.index.map(CENTROS)
    if len(red):
        g = g.join(red.groupby("hacia").agg(transferencias_recibe=("cantidad", "size"), valor_recibe=("valor", "sum")))
        g = g.join(red.groupby("desde").agg(transferencias_cede=("cantidad", "size"), valor_cede=("valor", "sum")))
        rutas = red.groupby(["desde", "hacia"]).agg(transferencias=("codigo", "size"), medicamentos=("codigo", "nunique"),
                                                   criticos=("critico", "sum"), valor=("valor", "sum")).reset_index()
    else:
        rutas = pd.DataFrame()
    g = g.fillna(0).reset_index()
    res = {
        "ventana": f"{ult[0]} a {ult[-1]}",
        "participacion_valor_pct": g.set_index("centro")["participacion_valor_pct"].to_dict(),
        "pct_en_cero_con_stock_en_otro": g.set_index("centro")["pct_en_cero_con_stock_en_otro"].to_dict(),
        "transferencias": int(len(red)), "transferencias_criticos": int(red["critico"].sum()) if len(red) else 0,
        "valor_transferencias_M": _r(red["valor"].sum() / 1e6, 2) if len(red) else 0,
    }
    return g, rutas, res


# ------------------------------------------------------------------- P5
def p5(kpi: pd.DataFrame, ia: list[dict]):
    k = kpi.set_index("periodo")
    antes = k[k.index < COMISION].tail(6)
    despues = k.tail(6)
    eventos = pd.DataFrame([{"fecha": (d.get("fecha_evento") or d.get("fecha_publicada") or "")[:10], "documento": d.get("id"),
                             "fuente": d.get("fuente"), "titulo": d.get("titulo"), "tipo_evento": d.get("tipo_evento"),
                             "riesgo": d.get("riesgo"), "resumen": d.get("resumen"), "url": d.get("url")}
                            for d in ia if (d.get("fecha_evento") or d.get("fecha_publicada") or "")[:4].isdigit()])
    if len(eventos):
        eventos = eventos[eventos["fecha"] >= "2021"].sort_values("fecha")
    res = {
        "hito": COMISION,
        "abastecimiento_antes_pct": _r(antes["pct_abastecimiento"].mean()), "abastecimiento_despues_pct": _r(despues["pct_abastecimiento"].mean()),
        "criticos_en_cero_antes": _r(antes["criticos_en_cero"].mean()), "criticos_en_cero_despues": _r(despues["criticos_en_cero"].mean()),
        "abastecimiento_en_hito_pct": _r(k.loc[COMISION, "pct_abastecimiento"]) if COMISION in k.index else None,
        "abastecimiento_ultimo_pct": _r(k["pct_abastecimiento"].iloc[-1]),
        "criticos_en_cero_en_hito": int(k.loc[COMISION, "criticos_en_cero"]) if COMISION in k.index else None,
        "criticos_en_cero_ultimo": int(k["criticos_en_cero"].iloc[-1]),
        "periodos_antes": f"{antes.index.min()} a {antes.index.max()}", "periodos_despues": f"{despues.index.min()} a {despues.index.max()}",
        "nota": "Relación temporal, no prueba de causa: en el mismo periodo hubo otras compras y cambios de gestión.",
    }
    return eventos, res


# ------------------------------------------------------------------- P6
def p6(tot: pd.DataFrame, med: pd.DataFrame, men: pd.DataFrame, fda: pd.DataFrame):
    periodos = sorted(tot["periodo"].unique())
    ult = periodos[-VENTANA:]
    vig = tot[tot["periodo"] == periodos[-1]]["codigo"]
    x = tot[tot["periodo"].isin(ult) & tot["codigo"].isin(vig)]
    z = x.groupby("codigo")["cantidad"].apply(lambda s: bool((s <= 0).all()) and len(s) >= VENTANA - 1)
    fantasmas = z[z].index
    ultimo_con_stock = tot[tot["cantidad"] > 0].groupby("codigo")["periodo"].max()
    f = med[med["codigo"].isin(fantasmas)][["codigo", "codigo_guiones", "descripcion", "principio_activo", "atc",
                                             "grupo_terapeutico", "categoria_critica", "critico", "precio_ultimo"]].copy()
    f["ultimo_mes_con_existencia"] = f["codigo"].map(ultimo_con_stock)
    if len(men):
        f["menciones_en_prensa"] = f["codigo"].map(men[men["codigo"].notna()].groupby("codigo")["documento"].nunique()).fillna(0).astype(int)
    if len(fda):
        f["escasez_eeuu"] = f["codigo"].map(fda.set_index("codigo")["escasez_eeuu_vigente"].groupby(level=0).max()).fillna(False)
    f = f.sort_values(["critico", "ultimo_mes_con_existencia"], ascending=[False, True])
    res = {
        "fantasmas": int(len(f)), "de_renglones_publicados": int(vig.nunique()),
        "criticos": int(f["critico"].sum()),
        "por_categoria": f["categoria_critica"].fillna(NO_CRITICO).value_counts().to_dict(),
        "nunca_con_existencia": int(f["ultimo_mes_con_existencia"].isna().sum()),
        "ejemplos_criticos": f[f["critico"]]["descripcion"].head(5).tolist(),
    }
    return f, res


# ------------------------------------------------------------------ main
def ejecutar(datos: Path = PROCESSED) -> dict:
    ex = pd.read_csv(datos / "existencias.csv", dtype={"codigo": str})
    ex = ex[~ex["atipico"].astype(bool)]
    med = pd.read_csv(datos / "medicamentos.csv", dtype={"codigo": str})
    kpi = _leer(datos, "kpi_mensual.csv")
    riesgo, red = _leer(datos, "riesgo_medicamentos.csv"), _leer(datos, "redistribucion.csv")
    men, fda = _leer(datos, "ia_menciones.csv"), _leer(datos, "cruce_fda.csv")
    ia = _jsonl(datos, "ia_documentos.jsonl")

    tot = ex.groupby(["periodo", "codigo"]).agg(cantidad=("cantidad", "sum"), valor=("valor", "sum"),
                                               precio=("precio_unitario", "first")).reset_index()
    opts = {"index": False, "encoding": "utf-8-sig"}
    s1, r1 = p1(tot, riesgo); s1.to_csv(datos / "p1_serie.csv", **opts)
    t2, r2 = p2(kpi, ia); t2.to_csv(datos / "p2_declaraciones.csv", **opts)
    t3, r3 = p3(tot, med, riesgo, fda); t3.to_csv(datos / "p3_grupos.csv", **opts)
    t4, rutas, r4 = p4(ex, red); t4.to_csv(datos / "p4_centros.csv", **opts); rutas.to_csv(datos / "p4_rutas.csv", **opts)
    t5, r5 = p5(kpi, ia); t5.to_csv(datos / "p5_eventos.csv", **opts)
    t6, r6 = p6(tot, med, men, fda); t6.to_csv(datos / "p6_fantasmas.csv", **opts)

    resumen = {"periodo": tot["periodo"].max(), "P1": r1, "P2": r2, "P3": r3, "P4": r4, "P5": r5, "P6": r6}
    (datos / "preguntas_resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return resumen


def main():
    ap = argparse.ArgumentParser(description="Tablas y cifras de las 6 preguntas del proyecto")
    ap.add_argument("--datos", type=Path, default=PROCESSED)
    a = ap.parse_args()
    print(json.dumps(ejecutar(a.datos), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
