"""Etapa 1 — Extracción.

Descarga las fuentes crudas a data/raw/:
  1. Inventarios de medicamentos de la CSS (CSV) desde el portal CKAN de datosabiertos.gob.pa
  2. Registros de escasez de medicamentos de openFDA (JSON)
  3. Noticias e informes sobre desabastecimiento (texto), listados en data/raw/texto/fuentes_texto.csv

Uso:
    python -m pipeline.extract            # todo
    python -m pipeline.extract --solo css # una sola fuente (css | openfda | texto)

Cada descarga queda registrada en data/raw/<fuente>/_manifest.json
(URL, fecha de descarga, tamaño y hash SHA-256) para trazabilidad.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from pipeline.config import CKAN_API, CSS_ORG, OPENFDA_SHORTAGES, RAW

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "css-pharma-supply-analytics/1.0 (proyecto academico UTP)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get(url: str, **kw) -> requests.Response:
    for intento in range(3):
        try:
            r = SESSION.get(url, timeout=60, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if intento == 2:
                raise
            print(f"   reintento {intento + 1} ({e})")
            time.sleep(2 * (intento + 1))
    raise RuntimeError("inalcanzable")


def _guardar_manifest(carpeta: Path, registros: list[dict]) -> None:
    (carpeta / "_manifest.json").write_text(
        json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------- 1. CSS
def extraer_css() -> list[dict]:
    """Busca en CKAN todos los datasets de medicamentos de la CSS y baja sus CSV."""
    destino = RAW / "css"
    destino.mkdir(parents=True, exist_ok=True)
    params = {"fq": f"organization:{CSS_ORG}", "q": "medicamentos", "rows": 1000}
    paquetes = _get(f"{CKAN_API}/package_search", params=params).json()["result"]["results"]
    paquetes = [p for p in paquetes if re.search(r"medicament", p["title"], re.I)
                and not re.search(r"quir", p["title"], re.I)]
    print(f"[CSS] {len(paquetes)} datasets de medicamentos encontrados")

    manifest = []
    for p in paquetes:
        for r in p["resources"]:
            if (r.get("format") or "").upper() != "CSV":
                continue
            nombre = r["url"].rsplit("/", 1)[-1]
            ruta = destino / nombre
            if ruta.exists() and ruta.stat().st_size > 0:
                contenido = ruta.read_bytes()
            else:
                print(f"   ↓ {nombre}")
                contenido = _get(r["url"]).content
                ruta.write_bytes(contenido)
            manifest.append({
                "archivo": nombre,
                "dataset": p["title"],
                "dataset_id": p["id"],
                "recurso": r.get("name"),
                "url": r["url"],
                "modificado_en_portal": r.get("last_modified") or r.get("created"),
                "licencia": p.get("license_title"),
                "bytes": len(contenido),
                "sha256": _sha256(contenido),
                "descargado": _now(),
            })
    _guardar_manifest(destino, manifest)
    print(f"[CSS] {len(manifest)} archivos CSV en {destino}")
    return manifest


# ------------------------------------------------------------ 2. openFDA
def extraer_openfda(pagina: int = 100) -> list[dict]:
    """Descarga todos los registros del endpoint Drug Shortages (paginado)."""
    destino = RAW / "openfda"
    destino.mkdir(parents=True, exist_ok=True)
    registros, skip, total = [], 0, None
    while total is None or skip < total:
        j = _get(OPENFDA_SHORTAGES, params={"limit": pagina, "skip": skip}).json()
        total = j["meta"]["results"]["total"]
        registros.extend(j["results"])
        skip += pagina
        print(f"[openFDA] {len(registros)}/{total}")
        time.sleep(0.3)
    contenido = json.dumps(registros, ensure_ascii=False).encode("utf-8")
    (destino / "drug_shortages.json").write_bytes(contenido)
    manifest = [{"archivo": "drug_shortages.json", "url": OPENFDA_SHORTAGES,
                 "registros": len(registros), "bytes": len(contenido),
                 "sha256": _sha256(contenido), "descargado": _now(),
                 "licencia": "openFDA — dominio público (CC0)"}]
    _guardar_manifest(destino, manifest)
    return manifest


# -------------------------------------------------------------- 3. Texto
def extraer_texto() -> list[dict]:
    """Descarga las páginas listadas en fuentes_texto.csv y guarda su texto plano."""
    from bs4 import BeautifulSoup

    destino = RAW / "texto"
    lista = destino / "fuentes_texto.csv"
    manifest = []
    with lista.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            nombre = f"{fila['id']}.txt"
            try:
                r = _get(fila["url"])
            except requests.RequestException as e:
                print(f"   ✗ {fila['id']}: {e}")
                continue
            if fila["url"].lower().endswith(".pdf"):
                (destino / f"{fila['id']}.pdf").write_bytes(r.content)
                texto = ""  # el PDF se convierte a texto en la etapa de transformación
            else:
                sopa = BeautifulSoup(r.text, "html.parser")
                for t in sopa(["script", "style", "nav", "footer", "header", "aside"]):
                    t.decompose()
                cuerpo = sopa.find("article") or sopa.body or sopa
                texto = re.sub(r"\n{3,}", "\n\n", cuerpo.get_text("\n", strip=True))
                (destino / nombre).write_text(texto, encoding="utf-8")
            manifest.append({**fila, "caracteres": len(texto), "descargado": _now()})
            print(f"   ↓ {fila['id']} ({len(texto)} caracteres)")
    _guardar_manifest(destino, manifest)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo", choices=["css", "openfda", "texto"])
    a = ap.parse_args()
    pasos = {"css": extraer_css, "openfda": extraer_openfda, "texto": extraer_texto}
    for nombre, fn in pasos.items():
        if a.solo in (None, nombre):
            fn()


if __name__ == "__main__":
    main()
