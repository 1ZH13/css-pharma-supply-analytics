"""Etapa 4 — Indicadores gerenciales (KPI), riesgo de desabastecimiento y redistribución.

Responde la pregunta gerencial del proyecto:
  ¿Qué medicamentos están en riesgo de desabastecimiento y cómo redistribuir el
  inventario entre los centros de distribución (CDPA, CDDI, CDCH)?

Entradas (data/processed): existencias, medicamentos, ia_menciones, cruce_fda.
Salidas  (data/processed):
| Tabla | Grano | Uso |
|---|---|---|
| `kpi_mensual.csv` | mes | valor del inventario, renglones en cero, críticos en cero |
| `kpi_centro.csv` | mes × centro | valor, participación y renglones en cero por centro |
| `riesgo_medicamentos.csv` | medicamento (último mes) | cobertura, consumo aparente, puntaje y nivel de riesgo |
| `redistribucion.csv` | medicamento × centro origen → destino | transferencias sugeridas |
| `kpi_resumen.json` | — | tarjetas del dashboard |

Supuestos (documentados en docs/kpi.md):
- **Consumo aparente**: la CSS publica existencias, no despachos. El consumo mensual se estima
  como la mediana de las disminuciones de existencia mes a mes en los últimos 12 meses
  (los meses con reposición se ignoran). Es una aproximación conservadora.
- Las filas marcadas `atipico` se excluyen.

Uso:  python -m pipeline.kpi  [--datos RUTA]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CENTROS, PROCESSED

VENTANA = 12             # meses para estimar consumo y frecuencia de quiebres
COB_OBJETIVO = 2.0       # meses de cobertura objetivo al redistribuir
COB_EXCESO = 4.0         # por encima de esto un centro puede ceder
COB_DEFICIT = 1.0        # por debajo de esto un centro necesita recibir


# ---------------------------------------------------------------- utilidades
def _consumo(serie: pd.Series) -> float:
    """Mediana de las caídas mes a mes (consumo aparente) en la ventana."""
    s = serie.dropna().tail(VENTANA + 1)
    caidas = -s.diff()
    caidas = caidas[caidas > 0]
    return float(caidas.median()) if len(caidas) else 0.0


def _racha_ceros(serie: pd.Series) -> int:
    n = 0
    for v in reversed(serie.dropna().tolist()):
        if v > 0:
            break
        n += 1
    return n


def _tendencia(serie: pd.Series, meses: int = 6) -> float | None:
    s = serie.dropna().tail(meses)
    if len(s) < 3 or s.iloc[: len(s) // 2].mean() <= 0:
        return None
    return float(s.iloc[len(s) // 2:].mean() / s.iloc[: len(s) // 2].mean() - 1)


# ------------------------------------------------------------------- KPI
def kpi_mensual(ex: pd.DataFrame, med: pd.DataFrame) -> pd.DataFrame:
    tot = ex.groupby(["periodo", "codigo"]).agg(cant=("cantidad", "sum"), valor=("valor", "sum")).reset_index()
    tot = tot.merge(med[["codigo", "critico"]], on="codigo", how="left")
    g = tot.groupby("periodo")
    k = pd.DataFrame({
        "valor_inventario": g["valor"].sum().round(2),
        "unidades": g["cant"].sum(),
        "renglones": g["codigo"].nunique(),
        "renglones_en_cero": g.apply(lambda x: int((x["cant"] <= 0).sum()), include_groups=False),
        "criticos": g.apply(lambda x: int(x["critico"].fillna(False).sum()), include_groups=False),
        "criticos_en_cero": g.apply(lambda x: int(((x["cant"] <= 0) & x["critico"].fillna(False)).sum()), include_groups=False),
    }).reset_index()
    k["pct_en_cero"] = (k["renglones_en_cero"] / k["renglones"] * 100).round(2)
    k["pct_abastecimiento"] = (100 - k["pct_en_cero"]).round(2)
    k["pct_criticos_en_cero"] = (k["criticos_en_cero"] / k["criticos"].replace(0, np.nan) * 100).round(2)
    k["variacion_valor_pct"] = (k["valor_inventario"].pct_change() * 100).round(2)
    k["anio"] = k["periodo"].str[:4].astype(int)
    return k


def kpi_centro(ex: pd.DataFrame) -> pd.DataFrame:
    g = ex.groupby(["periodo", "centro"])
    k = pd.DataFrame({
        "valor_inventario": g["valor"].sum().round(2),
        "unidades": g["cantidad"].sum(),
        "renglones": g["codigo"].nunique(),
        "renglones_en_cero": g.apply(lambda x: int((x["cantidad"] <= 0).sum()), include_groups=False),
    }).reset_index()
    k["pct_en_cero"] = (k["renglones_en_cero"] / k["renglones"] * 100).round(2)
    k["participacion_valor_pct"] = (k["valor_inventario"] / k.groupby("periodo")["valor_inventario"].transform("sum") * 100).round(2)
    k["nombre_centro"] = k["centro"].map(CENTROS)
    return k


# ------------------------------------------------------------- riesgo
def riesgo(ex: pd.DataFrame, med: pd.DataFrame, menciones: pd.DataFrame, fda: pd.DataFrame) -> pd.DataFrame:
    ultimo = ex["periodo"].max()
    total = ex.groupby(["codigo", "periodo"])["cantidad"].sum().unstack().sort_index(axis=1)
    centro = ex.pivot_table(index="codigo", columns=["centro", "periodo"], values="cantidad", aggfunc="sum")
    vigentes = total[ultimo].dropna().index          # renglones publicados en el último mes

    prensa = pd.Series(dtype=int)
    if not menciones.empty and "codigo" in menciones:
        f = menciones[menciones["situacion"].eq("faltante") & menciones["codigo"].notna()]
        prensa = f.groupby("codigo")["documento"].nunique()
    escasez = pd.Series(dtype=bool)
    if not fda.empty and "escasez_eeuu_vigente" in fda:
        escasez = fda.groupby("codigo")["escasez_eeuu_vigente"].max()

    filas = []
    for cod in vigentes:
        serie = total.loc[cod]
        exist = float(serie[ultimo])
        cons = _consumo(serie)
        cob = exist / cons if cons > 0 else (np.inf if exist > 0 else 0.0)
        ceros12 = int((serie.dropna().tail(VENTANA) <= 0).sum())
        racha = _racha_ceros(serie)
        tend = _tendencia(serie)
        m = med.loc[med["codigo"] == cod]
        critico = bool(m["critico"].iloc[0]) if len(m) else False
        n_prensa = int(prensa.get(cod, 0))
        eeuu = bool(escasez.get(cod, False))

        pts, motivos = 0, []
        if exist <= 0:
            pts += 40; motivos.append("sin existencia")
        elif cob < 1:
            pts += 35; motivos.append(f"cobertura {cob:.1f} meses")
        elif cob < 2:
            pts += 25; motivos.append(f"cobertura {cob:.1f} meses")
        elif cob < 3:
            pts += 15; motivos.append(f"cobertura {cob:.1f} meses")
        if ceros12:
            pts += min(20, 2 * ceros12); motivos.append(f"{ceros12} de {VENTANA} meses en cero")
        if tend is not None and tend < -0.3:
            pts += 10; motivos.append(f"existencias {tend * 100:.0f} % en 6 meses")
        if critico:
            pts += 15; motivos.append(f"crítico ({m['categoria_critica'].iloc[0]})")
        if n_prensa:
            pts += 10; motivos.append(f"faltante en {n_prensa} noticia(s)")
        if eeuu:
            pts += 5; motivos.append("escasez vigente en EE. UU.")
        pts = min(100, pts)

        fila = {"codigo": cod, "periodo": ultimo, "existencia_total": exist,
                "consumo_mensual_est": round(cons, 1),
                "cobertura_meses": None if np.isinf(cob) else round(cob, 2),
                "meses_en_cero_12m": ceros12, "racha_meses_en_cero": racha,
                "tendencia_6m_pct": None if tend is None else round(tend * 100, 1),
                "critico": critico, "faltante_en_prensa": n_prensa, "escasez_eeuu": eeuu,
                "puntaje_riesgo": pts, "nivel_riesgo": "alto" if pts >= 60 else ("medio" if pts >= 35 else "bajo"),
                "motivos": "; ".join(motivos)}
        for c in CENTROS:
            sc = centro[c].loc[cod] if (c in centro.columns.get_level_values(0) and cod in centro.index) else pd.Series(dtype=float)
            ec = float(sc.get(ultimo, 0) or 0)
            cc = _consumo(sc) if len(sc) else 0.0
            fila[f"existencia_{c}"] = ec
            fila[f"consumo_{c}"] = round(cc, 1)
            fila[f"cobertura_{c}"] = round(ec / cc, 2) if cc > 0 else None
        filas.append(fila)

    r = pd.DataFrame(filas).merge(
        med[["codigo", "descripcion", "principio_activo", "atc", "grupo_terapeutico", "categoria_critica", "precio_ultimo"]],
        on="codigo", how="left")
    r["valor_existencia"] = (r["existencia_total"] * r["precio_ultimo"]).round(2)
    return r.sort_values(["puntaje_riesgo", "critico"], ascending=False)


# -------------------------------------------------------- redistribución
def redistribucion(r: pd.DataFrame) -> pd.DataFrame:
    """Transferencias sugeridas: de centros con más de COB_EXCESO meses de cobertura a
    centros con menos de COB_DEFICIT, hasta llevarlos a COB_OBJETIVO sin bajar al origen
    de COB_OBJETIVO."""
    filas = []
    for x in r.itertuples():
        disp, nec = {}, {}
        for c in CENTROS:
            e, k = getattr(x, f"existencia_{c}"), getattr(x, f"consumo_{c}")
            if k <= 0:
                continue
            cob = e / k
            if cob > COB_EXCESO:
                disp[c] = e - COB_OBJETIVO * k
            elif cob < COB_DEFICIT:
                nec[c] = COB_OBJETIVO * k - e
        for d, falta in sorted(nec.items(), key=lambda t: -t[1]):
            for o in sorted(disp, key=lambda c: -disp[c]):
                if falta <= 0 or disp[o] <= 0:
                    continue
                q = float(np.floor(min(falta, disp[o])))
                if q <= 0:
                    continue
                disp[o] -= q
                falta -= q
                ko, kd = getattr(x, f"consumo_{o}"), getattr(x, f"consumo_{d}")
                filas.append({
                    "codigo": x.codigo, "descripcion": x.descripcion, "critico": x.critico,
                    "nivel_riesgo": x.nivel_riesgo, "desde": o, "hacia": d, "cantidad": q,
                    "valor": round(q * (x.precio_ultimo or 0), 2),
                    "cobertura_origen_antes": round(getattr(x, f"existencia_{o}") / ko, 2),
                    "cobertura_destino_antes": round(getattr(x, f"existencia_{d}") / kd, 2),
                    "cobertura_destino_despues": round((getattr(x, f"existencia_{d}") + q) / kd, 2),
                })
    out = pd.DataFrame(filas)
    return out.sort_values(["critico", "valor"], ascending=False) if len(out) else out


# ------------------------------------------------------------------ main
def ejecutar(datos: Path = PROCESSED) -> dict:
    ex = pd.read_csv(datos / "existencias.csv", dtype={"codigo": str})
    ex = ex[~ex["atipico"].astype(bool)]
    med = pd.read_csv(datos / "medicamentos.csv", dtype={"codigo": str})

    def leer(n):
        p = datos / n
        return pd.read_csv(p, dtype={"codigo": str}) if p.exists() and p.stat().st_size > 5 else pd.DataFrame()

    km, kc = kpi_mensual(ex, med), kpi_centro(ex)
    r = riesgo(ex, med, leer("ia_menciones.csv"), leer("cruce_fda.csv"))
    red = redistribucion(r)

    opts = {"index": False, "encoding": "utf-8-sig"}
    km.to_csv(datos / "kpi_mensual.csv", **opts)
    kc.to_csv(datos / "kpi_centro.csv", **opts)
    r.to_csv(datos / "riesgo_medicamentos.csv", **opts)
    red.to_csv(datos / "redistribucion.csv", **opts)

    u = km.iloc[-1]
    hace12 = km[km["periodo"] <= f"{int(u['periodo'][:4]) - 1}{u['periodo'][4:]}"].tail(1)
    resumen = {
        "periodo": u["periodo"],
        "valor_inventario": float(u["valor_inventario"]),
        "variacion_valor_12m_pct": round(float(u["valor_inventario"] / hace12["valor_inventario"].iloc[0] - 1) * 100, 1) if len(hace12) else None,
        "renglones": int(u["renglones"]), "pct_abastecimiento": float(u["pct_abastecimiento"]),
        "renglones_en_cero": int(u["renglones_en_cero"]), "criticos_en_cero": int(u["criticos_en_cero"]),
        "riesgo_alto": int((r["nivel_riesgo"] == "alto").sum()), "riesgo_medio": int((r["nivel_riesgo"] == "medio").sum()),
        "criticos_riesgo_alto": int(((r["nivel_riesgo"] == "alto") & r["critico"]).sum()),
        "cobertura_mediana_meses": float(r["cobertura_meses"].dropna().median()),
        "transferencias_sugeridas": int(len(red)),
        "valor_transferencias": float(red["valor"].sum()) if len(red) else 0.0,
        "centros_en_cero": kc[kc["periodo"] == u["periodo"]].set_index("centro")["pct_en_cero"].to_dict(),
    }
    (datos / "kpi_resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumen


def main():
    ap = argparse.ArgumentParser(description="KPI, riesgo de desabastecimiento y redistribución")
    ap.add_argument("--datos", type=Path, default=PROCESSED)
    a = ap.parse_args()
    print(json.dumps(ejecutar(a.datos), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
