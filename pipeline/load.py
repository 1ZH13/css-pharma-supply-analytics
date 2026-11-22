"""Carga de las tablas limpias en MongoDB Atlas.

Cada colección se carga primero en una colección temporal y luego se reemplaza de
forma atómica (`renameCollection` con `dropTarget`), de modo que el dashboard nunca
lee una colección a medio cargar. Cada ejecución queda registrada en `ejecuciones`.

| Colección | Contenido | Tipo de dato de origen |
|---|---|---|
| `existencias` | medicamento × mes × centro | estructurado (CSV CSS) |
| `medicamentos` | catálogo con ATC y categoría crítica | estructurado (CSV CSS) |
| `totales_referencia` | totales nacionales publicados | estructurado (CSV CSS) |
| `fda_escasez` | registros originales de openFDA | semiestructurado (JSON) |
| `documentos` | noticias e informes con su texto | no estructurado (texto) |
| `ia_documentos`, `ia_menciones`, `ia_causas` | análisis de Gemini sobre el texto | IA generativa |
| `inn_equivalencias`, `cruce_fda` | principio activo ES → EN y escasez en EE. UU. | IA + JSON |
| `kpi_mensual`, `kpi_centro`, `kpi_resumen` | indicadores gerenciales | Etapa 4 |
| `riesgo_medicamentos`, `redistribucion` | riesgo por medicamento y transferencias sugeridas | Etapa 4 |
| `incidencias`, `calidad`, `ejecuciones` | trazabilidad del pipeline | — |

Requiere la variable de entorno MONGODB_URI (archivo `.env` o secreto de GitHub).
Uso:  python -m pipeline.load  [--datos RUTA] [--raw RUTA]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import PROCESSED, RAW

LOTE = 5000


def _registros(df: pd.DataFrame) -> list[dict]:
    out = []
    for r in df.to_dict("records"):
        out.append({k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()})
    return out


def _reemplazar(db, nombre: str, docs: list[dict], indices: list | None = None) -> int:
    tmp = db[f"{nombre}__carga"]
    tmp.drop()
    for i in range(0, len(docs), LOTE):
        tmp.insert_many(docs[i:i + LOTE], ordered=False)
    for idx in indices or []:
        tmp.create_index(idx)
    if docs:
        tmp.rename(nombre, dropTarget=True)
    return len(docs)


def cargar(datos: Path, raw: Path, uri: str, base: str) -> dict:
    from pymongo import ASCENDING, MongoClient
    from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

    try:
        cli = MongoClient(uri, serverSelectionTimeoutMS=20000, appname="css-pharma-supply-analytics")
        cli.admin.command("ping")
    except ServerSelectionTimeoutError:
        sys.exit("No se pudo conectar con MongoDB Atlas. Revise en Atlas → Network Access que la IP "
                 "de este equipo esté permitida (para GitHub Actions: 0.0.0.0/0) y que el cluster no esté pausado.")
    except OperationFailure as e:
        sys.exit(f"Atlas rechazó las credenciales de MONGODB_URI (usuario o contraseña): {e.code}")
    except ConfigurationError as e:
        sys.exit(f"MONGODB_URI mal formada: {e}")
    db = cli[base]
    inicio = datetime.now(timezone.utc)
    n = {}

    ex = pd.read_csv(datos / "existencias.csv", dtype={"codigo": str})
    n["existencias"] = _reemplazar(db, "existencias", _registros(ex), [
        [("codigo", ASCENDING), ("periodo", ASCENDING)], [("periodo", ASCENDING), ("centro", ASCENDING)]])

    med = pd.read_csv(datos / "medicamentos.csv", dtype={"codigo": str})
    docs = _registros(med)
    for d in docs:
        d["_id"] = d["codigo"]
    n["medicamentos"] = _reemplazar(db, "medicamentos", docs, [[("atc", ASCENDING)], [("critico", ASCENDING)]])

    ref = datos / "totales_referencia.csv"
    if ref.exists() and ref.stat().st_size > 5:
        n["totales_referencia"] = _reemplazar(db, "totales_referencia",
                                              _registros(pd.read_csv(ref, dtype={"codigo": str})),
                                              [[("codigo", ASCENDING), ("periodo", ASCENDING)]])

    # openFDA se guarda con su estructura JSON original (documentos anidados)
    fda_json = raw / "openfda" / "drug_shortages.json"
    if fda_json.exists():
        d = json.loads(fda_json.read_text(encoding="utf-8"))
        fda = d.get("results", d) if isinstance(d, dict) else d
    else:
        fda = _registros(pd.read_csv(datos / "fda_escasez.csv"))
    n["fda_escasez"] = _reemplazar(db, "fda_escasez", fda, [[("generic_name", ASCENDING)], [("status", ASCENDING)]])

    docs = [json.loads(l) for l in (datos / "documentos.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    for d in docs:
        d["_id"] = d.get("id")
    n["documentos"] = _reemplazar(db, "documentos", docs)

    # Etapa 3: resultados de la IA generativa (si existen)
    ia = datos / "ia_documentos.jsonl"
    if ia.exists():
        docs = [json.loads(l) for l in ia.read_text(encoding="utf-8").splitlines() if l.strip()]
        for d in docs:
            d["_id"] = d.get("id")
        n["ia_documentos"] = _reemplazar(db, "ia_documentos", docs, [[("tipo_evento", ASCENDING)], [("riesgo", ASCENDING)]])
    for nombre, idx in (("ia_menciones", [("codigo", ASCENDING)]), ("ia_causas", [("causa", ASCENDING)]),
                        ("inn_equivalencias", [("principio_activo", ASCENDING)]), ("cruce_fda", [("codigo", ASCENDING)])):
        ruta = datos / f"{nombre}.csv"
        if ruta.exists() and ruta.stat().st_size > 5:
            n[nombre] = _reemplazar(db, nombre, _registros(pd.read_csv(ruta, dtype={"codigo": str})), [idx])

    # Etapa 4: indicadores y riesgo
    for nombre, idx in (("kpi_mensual", [("periodo", ASCENDING)]), ("kpi_centro", [("periodo", ASCENDING), ("centro", ASCENDING)]),
                        ("riesgo_medicamentos", [("puntaje_riesgo", ASCENDING)]), ("redistribucion", [("codigo", ASCENDING)])):
        ruta = datos / f"{nombre}.csv"
        if ruta.exists() and ruta.stat().st_size > 5:
            n[nombre] = _reemplazar(db, nombre, _registros(pd.read_csv(ruta, dtype={"codigo": str})), [idx])
    # Las 6 preguntas y su narrativa
    for nombre in ("p1_serie", "p2_declaraciones", "p3_grupos", "p4_centros", "p4_rutas", "p5_eventos", "p6_fantasmas"):
        ruta = datos / f"{nombre}.csv"
        if ruta.exists() and ruta.stat().st_size > 5:
            n[nombre] = _reemplazar(db, nombre, _registros(pd.read_csv(ruta, dtype={"codigo": str})))
    for nombre in ("preguntas_resumen", "narrativa"):
        ruta = datos / f"{nombre}.json"
        if ruta.exists():
            db[nombre].replace_one({"_id": "ultimo"}, {**json.loads(ruta.read_text(encoding="utf-8")), "_id": "ultimo"}, upsert=True)
    res = datos / "kpi_resumen.json"
    if res.exists():
        db["kpi_resumen"].replace_one({"_id": "ultimo"}, {**json.loads(res.read_text(encoding="utf-8")), "_id": "ultimo"}, upsert=True)

    n["incidencias"] = _reemplazar(db, "incidencias",
                                   _registros(pd.read_csv(datos / "incidencias.csv", dtype={"codigo": str})),
                                   [[("tipo", ASCENDING)]])

    cal = datos / "calidad.json"
    if cal.exists():
        c = json.loads(cal.read_text(encoding="utf-8"))
        c["_id"] = "ultimo"
        db["calidad"].replace_one({"_id": "ultimo"}, c, upsert=True)

    reg = {"inicio": inicio, "fin": datetime.now(timezone.utc), "documentos": n,
           "origen": os.getenv("GITHUB_RUN_ID") and f"github-actions run {os.getenv('GITHUB_RUN_NUMBER')}" or "local"}
    db["ejecuciones"].insert_one(reg)
    cli.close()
    return n


def main():
    ap = argparse.ArgumentParser(description="Carga en MongoDB Atlas")
    ap.add_argument("--datos", type=Path, default=PROCESSED)
    ap.add_argument("--raw", type=Path, default=RAW)
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    uri = os.getenv("MONGODB_URI")
    if not uri:
        sys.exit("Falta MONGODB_URI (en .env o como secreto del repositorio).")
    base = os.getenv("MONGODB_DB", "css_pharma")
    n = cargar(a.datos, a.raw, uri, base)
    print(json.dumps({"base": base, "colecciones": n}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
