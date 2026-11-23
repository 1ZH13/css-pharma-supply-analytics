"""Extracción del cuerpo de una noticia a partir de su HTML.

Cada medio arma la página de forma distinta, así que se prueban dos estrategias:

1. **JSON-LD** (`<script type="application/ld+json">` con `articleBody`): lo publican
   La Prensa, TVN y Telemetro para los buscadores y trae el texto completo y limpio.
2. **Densidad de párrafos**: se toman los `<p>` con al menos 40 caracteres y se busca
   el contenedor más profundo que reúne el 60 % o más de ese texto. Así se descartan
   menús, titulares relacionados y pies de página (La Estrella, Panamá América).
"""
from __future__ import annotations

import html
import json
import re

from bs4 import BeautifulSoup

MIN_PARRAFO = 40
UMBRAL_CONTENEDOR = 0.6
MIN_JSONLD = 400


def _articlebody(sopa: BeautifulSoup) -> str:
    mejor = ""

    def recorrer(o):
        nonlocal mejor
        if isinstance(o, list):
            for x in o:
                recorrer(x)
        elif isinstance(o, dict):
            cuerpo = o.get("articleBody")
            if isinstance(cuerpo, str) and len(cuerpo) > len(mejor):
                mejor = cuerpo
            for v in o.values():
                recorrer(v)

    for s in sopa.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            recorrer(json.loads(s.string or s.get_text() or ""))
        except (json.JSONDecodeError, TypeError):
            continue
    # Algunos medios guardan el cuerpo con etiquetas o entidades HTML
    if "<" in mejor:
        mejor = BeautifulSoup(mejor, "html.parser").get_text("\n")
    return html.unescape(mejor).strip()


def _por_parrafos(sopa: BeautifulSoup) -> str:
    for t in sopa(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        t.decompose()
    parrafos = [p for p in sopa.find_all("p") if len(p.get_text(" ", strip=True)) >= MIN_PARRAFO]
    if not parrafos:
        return ""
    largo = {id(p): len(p.get_text(" ", strip=True)) for p in parrafos}
    total = sum(largo.values())
    peso, nodo, prof = {}, {}, {}
    for p in parrafos:
        for k, anc in enumerate(reversed(list(p.parents))):
            peso[id(anc)] = peso.get(id(anc), 0) + largo[id(p)]
            nodo[id(anc)] = anc
            prof[id(anc)] = k
    elegibles = [i for i, w in peso.items() if w >= UMBRAL_CONTENEDOR * total]
    contenedor = nodo[max(elegibles, key=lambda i: prof[i])]
    dentro = [p for p in parrafos if contenedor in p.parents]
    return "\n\n".join(p.get_text(" ", strip=True) for p in dentro)


def extraer_articulo(contenido_html: str) -> tuple[str, str]:
    """Devuelve (texto, método) — método: `jsonld`, `parrafos` o `vacio`."""
    sopa = BeautifulSoup(contenido_html, "html.parser")
    cuerpo = _articlebody(sopa)
    if len(cuerpo) >= MIN_JSONLD:
        return _normalizar(cuerpo), "jsonld"
    texto = _por_parrafos(sopa)
    if texto:
        return _normalizar(texto), "parrafos"
    return "", "vacio"


def _normalizar(t: str) -> str:
    t = t.replace("\xa0", " ").replace("\r", "")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()
