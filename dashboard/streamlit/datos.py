"""Capa de datos del dashboard.

Orden de lectura: 1) MongoDB Atlas (si hay MONGODB_URI en los secretos de Streamlit o en
el entorno), 2) carpeta local `data/processed`, 3) tablas publicadas en la rama `data` de
GitHub. Así la demo funciona aunque falle una de las fuentes.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

RAIZ = Path(__file__).resolve().parents[2]
LOCAL = Path(os.getenv("DATOS_LOCAL", RAIZ / "data" / "processed"))
GITHUB = "https://raw.githubusercontent.com/1ZH13/css-pharma-supply-analytics/data/processed/"
BASE = "css_pharma"


def secreto(nombre: str) -> str | None:
    try:
        v = st.secrets.get(nombre)
        if v:
            return str(v)
    except Exception:
        pass
    return os.getenv(nombre)


@st.cache_resource(show_spinner=False)
def _db():
    uri = secreto("MONGODB_URI")
    if not uri:
        return None
    try:
        from pymongo import MongoClient
        cli = MongoClient(uri, serverSelectionTimeoutMS=6000, appname="css-pharma-dashboard")
        cli.admin.command("ping")
        return cli[secreto("MONGODB_DB") or BASE]
    except Exception:
        return None


def origen() -> str:
    if _db() is not None:
        return "MongoDB Atlas"
    if (LOCAL / "kpi_mensual.csv").exists():
        return "archivos locales"
    return "GitHub (rama data)"


@st.cache_data(ttl=3600, show_spinner=False)
def tabla(nombre: str, filtro: tuple | None = None) -> pd.DataFrame:
    db = _db()
    if db is not None and nombre in db.list_collection_names():
        q = dict([filtro]) if filtro else {}
        df = pd.DataFrame(list(db[nombre].find(q, {"_id": 0})))
    elif (LOCAL / f"{nombre}.csv").exists():
        df = pd.read_csv(LOCAL / f"{nombre}.csv", dtype={"codigo": str})
    else:
        r = requests.get(GITHUB + f"{nombre}.csv", timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")), dtype={"codigo": str})
    if filtro and len(df) and filtro[0] in df:
        df = df[df[filtro[0]] == filtro[1]]
    if "codigo" in df:
        df["codigo"] = df["codigo"].astype(str)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def documento(nombre: str) -> dict:
    db = _db()
    if db is not None and nombre in db.list_collection_names():
        d = db[nombre].find_one({"_id": "ultimo"}, {"_id": 0})
        if d:
            return d
    if (LOCAL / f"{nombre}.json").exists():
        return json.loads((LOCAL / f"{nombre}.json").read_text(encoding="utf-8"))
    r = requests.get(GITHUB + f"{nombre}.json", timeout=30)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=3600, show_spinner=False)
def jsonl(nombre: str) -> list[dict]:
    db = _db()
    if db is not None and nombre in db.list_collection_names():
        return list(db[nombre].find({}, {"_id": 0}))
    if (LOCAL / f"{nombre}.jsonl").exists():
        txt = (LOCAL / f"{nombre}.jsonl").read_text(encoding="utf-8")
    else:
        r = requests.get(GITHUB + f"{nombre}.jsonl", timeout=30)
        r.raise_for_status()
        txt = r.content.decode("utf-8")
    return [json.loads(l) for l in txt.splitlines() if l.strip()]


def historia(codigo: str) -> pd.DataFrame:
    """Existencias mensuales de un medicamento por centro."""
    return tabla("existencias", ("codigo", codigo))
