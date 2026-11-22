"""Reporte de calidad de datos de la Etapa 2.

Lee las tablas de `data/processed/` y genera:
- `reporte_calidad.md`  — reporte legible (se incluye en el documento del proyecto)
- `calidad.json`        — indicadores para MongoDB y el dashboard

Dimensiones evaluadas: completitud, validez, consistencia, unicidad y exactitud
(validación cruzada contra los totales que la propia CSS publica en sus cuadros comparativos).

Uso:  python -m pipeline.quality  [--datos RUTA]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import PROCESSED

EXPLICACION = {
    "precio_publicado_redondeado": "La CSS publica el precio con 2 decimales pero calcula el monto con el precio completo. Se usa el precio efectivo (monto ÷ cantidad).",
    "monto_no_cuadra": "El monto publicado no coincide con cantidad × precio (más de 1 %). Se conserva la cantidad; el valor se recalcula.",
    "total_no_cuadra": "La suma de los tres centros no coincide con el total publicado. Se usa la suma de los centros.",
    "cantidad_atipica": "Total del mes más de 20 veces la mediana del medicamento. Se marca `atipico = true` y se excluye de los KPI.",
    "existencia_negativa": "Existencia menor que cero en la fuente.",
    "sin_codigo_atc": "Medicamento sin código SAFIRO/ATC (no aparece en los cuadros comparativos).",
    "codigo_con_varias_descripciones": "El mismo código aparece con nombres distintos (variantes de escritura o reutilización).",
    "sin_precio": "Ningún archivo informa precio para el medicamento.",
    "mes_sin_datos": "El nombre del archivo incluye el mes pero no trae valores.",
    "codigo_duplicado_en_archivo": "El código aparece dos veces en el mismo archivo y mes. Se conserva la primera fila.",
    "mes_repetido_con_valores_distintos": "El mismo mes viene en dos archivos con cifras distintas. Se conserva el más reciente.",
    "archivo_excluido": "Archivo fuera del alcance (insumos médico-quirúrgicos).",
    "error_de_lectura": "El archivo no se pudo interpretar.",
    "texto_incompleto": "La noticia se descargó pero el texto útil tiene menos de 500 caracteres.",
    "texto_sin_descarga": "La noticia o el informe no se pudo descargar.",
    "openfda_sin_nombre": "Registros de openFDA sin nombre genérico.",
}


def _meses(desde: str, hasta: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(desde, hasta, freq="M")]


def evaluar(d: Path) -> dict:
    ex = pd.read_csv(d / "existencias.csv", dtype={"codigo": str})
    med = pd.read_csv(d / "medicamentos.csv", dtype={"codigo": str})
    inc = pd.read_csv(d / "incidencias.csv", dtype={"codigo": str})
    ref = pd.read_csv(d / "totales_referencia.csv", dtype={"codigo": str}) if (d / "totales_referencia.csv").stat().st_size > 5 else pd.DataFrame()
    lec = pd.read_csv(d / "lectura_archivos.csv")
    fda = pd.read_csv(d / "fda_escasez.csv")
    docs = [json.loads(l) for l in (d / "documentos.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    todos = _meses(ex["periodo"].min(), ex["periodo"].max())
    presentes = sorted(ex["periodo"].unique())
    faltan = [p for p in todos if p not in presentes]

    filas_mes = ex.groupby(["codigo", "periodo"]).agg(cant=("cantidad", "sum"), atip=("atipico", "max")).reset_index()
    unicidad = 1 - ex.duplicated(["codigo", "periodo", "centro"]).mean()

    cruce = {}
    if not ref.empty:
        m = ref.merge(filas_mes, on=["codigo", "periodo"])
        m["ok"] = (m["total_reportado"] - m["cant"]).abs() < 0.5
        cruce = {a: {"comparaciones": int(len(g)), "coinciden": round(float(g["ok"].mean()) * 100, 2)}
                 for a, g in m.groupby(m["periodo"].str[:4])}

    ind = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cobertura": {"desde": todos[0], "hasta": todos[-1], "meses_esperados": len(todos),
                      "meses_con_datos": len(presentes), "meses_faltantes": faltan},
        "volumen": {"filas_existencias": int(len(ex)), "medicamentos": int(len(med)),
                    "renglones_por_mes_promedio": round(float(ex.groupby("periodo")["codigo"].nunique().mean()), 1),
                    "archivos_leidos": int(len(lec)), "fda_registros": int(len(fda)), "documentos": len(docs)},
        "completitud": {
            "meses_con_dato_pct": round(len(presentes) / len(todos) * 100, 1),
            "precio_imputado_pct": round(float(ex["precio_imputado"].mean()) * 100, 2),
            "medicamentos_con_atc_pct": round(float(med["atc"].notna().mean()) * 100, 1),
            "documentos_texto_ok": sum(1 for x in docs if x["estado"] == "ok"),
        },
        "validez": {"filas_atipicas_pct": round(float(filas_mes["atip"].mean()) * 100, 3),
                    "renglones_atipicos": int(filas_mes["atip"].sum())},
        "unicidad_pct": round(float(unicidad) * 100, 3),
        "exactitud_vs_cuadros_comparativos": cruce,
        "incidencias_por_tipo": inc["tipo"].value_counts().to_dict(),
        "archivos": lec.to_dict("records"),
        "atipicos_por_mes": filas_mes[filas_mes["atip"]].groupby("periodo").size().to_dict(),
    }
    return ind


def a_markdown(i: dict) -> str:
    c, v, comp = i["cobertura"], i["volumen"], i["completitud"]
    L = [
        "# Reporte de calidad de datos — Inventario de medicamentos CSS",
        "",
        f"_Generado automáticamente por `pipeline/quality.py` el {i['generado'][:10]}._",
        "",
        "## Resumen",
        "",
        "| Indicador | Valor |",
        "|---|---|",
        f"| Período cubierto | {c['desde']} a {c['hasta']} |",
        f"| Meses con datos | {c['meses_con_datos']} de {c['meses_esperados']} ({comp['meses_con_dato_pct']} %) |",
        f"| Meses sin publicación | {', '.join(c['meses_faltantes']) or 'ninguno'} |",
        f"| Archivos CSV leídos | {v['archivos_leidos']} |",
        f"| Filas de existencias (medicamento × mes × centro) | {v['filas_existencias']:,} |",
        f"| Medicamentos distintos | {v['medicamentos']} (promedio {v['renglones_por_mes_promedio']} por mes) |",
        f"| Medicamentos con código ATC | {comp['medicamentos_con_atc_pct']} % |",
        f"| Filas con precio imputado (ene–jul 2021) | {comp['precio_imputado_pct']} % |",
        f"| Unicidad (sin duplicados medicamento-mes-centro) | {i['unicidad_pct']} % |",
        f"| Renglones-mes atípicos | {i['validez']['renglones_atipicos']} ({i['validez']['filas_atipicas_pct']} %) |",
        f"| Registros openFDA | {v['fda_registros']:,} |",
        f"| Documentos de texto con contenido útil | {comp['documentos_texto_ok']} de {v['documentos']} |",
        "",
        "## Exactitud: validación cruzada",
        "",
        "Los totales nacionales calculados (suma de CDPA + CDDI + CDCH) se comparan con los que la CSS publica en sus *cuadros comparativos*.",
        "",
        "| Año | Comparaciones | Coinciden |",
        "|---|---|---|",
    ]
    for a, x in i["exactitud_vs_cuadros_comparativos"].items():
        L.append(f"| {a} | {x['comparaciones']:,} | {x['coinciden']} % |")
    L += ["", "## Incidencias detectadas y tratamiento", "", "| Tipo | Casos | Tratamiento |", "|---|---|---|"]
    for t, n in i["incidencias_por_tipo"].items():
        L.append(f"| `{t}` | {n:,} | {EXPLICACION.get(t, '')} |")
    if i["atipicos_por_mes"]:
        L += ["", "### Meses con más renglones atípicos", ""]
        top = sorted(i["atipicos_por_mes"].items(), key=lambda x: -x[1])[:5]
        L += [f"- **{p}**: {n} renglones" for p, n in top]
        L += ["", "Agosto de 2024 concentra la mayoría: la publicación oficial (y su cuadro comparativo) trae cantidades "
                  "decenas de veces superiores al resto del año. Se conservan, pero se excluyen de los indicadores."]
    L += ["", "## Formatos de origen", "",
          "| Archivo | Familia | Codificación | Separador | Encabezado | Filas |", "|---|---|---|---|---|---|"]
    for a in i["archivos"]:
        enc = {True: "sí", False: "no"}.get(a.get("encabezado"), "—")
        L.append(f"| {a['archivo']} | {a['familia']} | {a.get('codificacion') or '—'} | "
                 f"`{a.get('separador') or '—'}` | {enc} | {int(a['filas']):,} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Reporte de calidad de datos")
    ap.add_argument("--datos", type=Path, default=PROCESSED)
    a = ap.parse_args()
    ind = evaluar(a.datos)
    (a.datos / "calidad.json").write_text(json.dumps(ind, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (a.datos / "reporte_calidad.md").write_text(a_markdown(ind), encoding="utf-8")
    print(json.dumps({k: ind[k] for k in ("cobertura", "completitud", "exactitud_vs_cuadros_comparativos")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
