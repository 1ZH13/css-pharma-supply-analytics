"""IA generativa (uso 2): Gemini redacta los hallazgos de las 6 preguntas.

Recibe SOLO las cifras calculadas en `preguntas_resumen.json` y devuelve, por pregunta,
un titular (afirmación, no tema), el hallazgo, la implicación para la decisión y la cautela
metodológica. Se le prohíbe usar cifras que no estén en la entrada; el resultado se valida:
cada número del texto debe aparecer en la entrada (si no, se marca para revisión).

La respuesta se guarda en caché por hash de las cifras: si los datos no cambian, no se
vuelve a consultar a Gemini. Si Gemini no está disponible se usa una redacción de plantilla.

Salida: data/processed/narrativa.json
Uso:    python -m pipeline.narrativa  [--datos RUTA]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from pathlib import Path

from .config import PROCESSED
from .ia import ClienteGemini, ErrorIA

log = logging.getLogger("narrativa")
VERSION = "v1"
# Narrativa publicada en la rama data: en GitHub Actions la carpeta de trabajo empieza vacía,
# así que la caché se toma de ahí para no volver a consultar a Gemini si las cifras no cambiaron.
PUBLICADA = "https://raw.githubusercontent.com/1ZH13/css-pharma-supply-analytics/data/processed/narrativa.json"


def _previa(salida: Path) -> dict:
    if salida.exists():
        return json.loads(salida.read_text(encoding="utf-8"))
    try:
        import requests
        r = requests.get(PUBLICADA, timeout=20)
        if r.ok:
            return r.json()
    except Exception as e:  # sin red o sin rama data: se redacta de nuevo
        log.info("Sin narrativa publicada previa: %s", e)
    return {}

PREGUNTAS = {
    "P1": "¿Qué pasó con el inventario de la CSS en 2025?",
    "P2": "¿Es real el \"90 % de abastecimiento\" que anuncia la CSS?",
    "P3": "¿Quiénes pagan el desabastecimiento?",
    "P4": "¿El interior del país está peor abastecido?",
    "P5": "¿Funcionó la Comisión de Desabastecimiento Crítico?",
    "P6": "¿Cuáles son los medicamentos \"fantasma\"?",
}

ESQUEMA = {"type": "OBJECT", "properties": {"preguntas": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "id": {"type": "STRING", "enum": list(PREGUNTAS)},
    "titular": {"type": "STRING", "description": "afirmación de máximo 12 palabras con la cifra principal"},
    "hallazgo": {"type": "STRING", "description": "2 o 3 oraciones con las cifras clave"},
    "implicacion": {"type": "STRING", "description": "1 o 2 oraciones: qué decisión habilita y para quién"},
    "cautela": {"type": "STRING", "description": "1 oración: limitación del dato"}},
    "required": ["id", "titular", "hallazgo", "implicacion", "cautela"]}}}, "required": ["preguntas"]}

PROMPT = """Eres analista de un Sistema de Información Gerencial para la Caja de Seguro Social (CSS) de Panamá.
Redacta, en español claro para gerentes, los hallazgos de estas 6 preguntas.

Reglas estrictas:
- Usa SOLO las cifras del JSON de entrada; no inventes números, fechas ni nombres.
- Redondea como en la entrada. Escribe "B/." para balboas y "%" pegado al número con espacio (p. ej. "86.3 %").
- El titular es una afirmación (no un tema), máximo 12 palabras, con la cifra más importante.
- Sé neutral: describe lo que muestran los datos públicos de la CSS, sin acusar.
- En "cautela" menciona la limitación indicada en la entrada si la hay (p. ej. almacén central vs farmacias,
  relación temporal no causal, consumo estimado).

Preguntas:
{preguntas}

Cifras calculadas (JSON):
{cifras}
"""


def _numeros(texto: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d+(?:[.,]\d+)?", texto)}


def _validar(item: dict, cifras_json: str) -> list[str]:
    permitidos = _numeros(cifras_json) | {str(i) for i in range(0, 13)} | {"2021", "2022", "2023", "2024", "2025", "2026"}
    texto = " ".join(str(item.get(k, "")) for k in ("titular", "hallazgo", "implicacion", "cautela"))
    return sorted(n for n in _numeros(texto) if n not in permitidos and n.rstrip("0").rstrip(".") not in permitidos)


def _n(x) -> str:
    """90.0 -> '90'; 86.3 -> '86.3' (mismo formato que el documento y Power BI)."""
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def titulares_fijos(r: dict) -> dict:
    """Titulares con cifras fijas para P2 y P5.

    Gemini puede elegir otra cifra válida (el máximo declarado o los promedios de 6 meses);
    estos titulares usan siempre las mismas cifras que el documento, la presentación y Power BI.
    """
    p2, p5 = r["P2"], r["P5"]
    anio, mes = str(p5.get("hito", "2025-10")).split("-")
    return {
        "P2": f"Se anuncian {_n(p2['pct_declarado_min'])}–{_n(p2['pct_declarado_max'])} % de abastecimiento; "
              f"los datos muestran {_n(p2['pct_datos_12m_min'])}–{_n(p2['pct_datos_12m_max'])} %",
        "P5": f"Desde la Comisión ({MESES[int(mes) - 1]}-{anio}) el abastecimiento subió de "
              f"{_n(p5['abastecimiento_en_hito_pct'])} % a {_n(p5['abastecimiento_ultimo_pct'])} %",
    }


def _fijar(out: dict, cifras: dict) -> dict:
    for k, t in titulares_fijos(cifras).items():
        out["preguntas"][k]["titular"] = t
    return out


def plantilla(r: dict) -> dict:
    """Redacción de respaldo sin IA."""
    p1, p2, p3, p4, p5, p6 = (r[k] for k in ("P1", "P2", "P3", "P4", "P5", "P6"))
    top = p3["top3"][0] if p3.get("top3") else {"grupo": "", "pct_meses_en_cero": ""}
    return {"P1": {"titular": f"El inventario cayó {abs(p1['cambio_valor_pct'])} % en valor al iniciar 2025",
                   "hallazgo": f"Entre {p1['corte']} la cantidad bajó {p1['cambio_cantidad_pct']} % y el valor {p1['cambio_valor_pct']} % con precios estables.",
                   "implicacion": "Definir si el nuevo nivel de inventario es una política deliberada o un riesgo a corregir.",
                   "cautela": "Se comparan existencias publicadas, no consumo real."},
            "P2": {"titular": f"Se anuncian {p2['pct_declarado_min']}–{p2['pct_declarado_max']} %; los datos muestran {p2['pct_datos_ultimo']} %",
                   "hallazgo": f"En 12 meses el abastecimiento de los almacenes osciló entre {p2['pct_datos_12m_min']} % y {p2['pct_datos_12m_max']} %.",
                   "implicacion": "Acordar un indicador único y público de abastecimiento.", "cautela": p2.get("nota", "")},
            "P3": {"titular": f"{top['grupo']}: {top['pct_meses_en_cero']} % de meses sin existencia",
                   "hallazgo": f"Los no críticos promedian {p3['pct_no_criticos']} %.",
                   "implicacion": "Priorizar compras y stock de seguridad por grupo de pacientes.", "cautela": "Ventana de 12 meses."},
            "P4": {"titular": f"Panamá concentra {p4['participacion_valor_pct'].get('CDPA')} % del inventario",
                   "hallazgo": f"{p4['transferencias']} traslados sugeridos por B/. {p4['valor_transferencias_M']} millones.",
                   "implicacion": "Ejecutar traslados antes de comprar.", "cautela": "Consumo por centro estimado."},
            "P5": {"titular": f"El abastecimiento subió de {p5['abastecimiento_en_hito_pct']} % a {p5['abastecimiento_ultimo_pct']} %",
                   "hallazgo": f"Críticos en cero: {p5['criticos_en_cero_en_hito']} → {p5['criticos_en_cero_ultimo']}.",
                   "implicacion": "Evaluar mantener la compra conjunta.", "cautela": p5.get("nota", "")},
            "P6": {"titular": f"{p6['fantasmas']} medicamentos llevan 12 meses en cero",
                   "hallazgo": f"{p6['criticos']} son críticos.", "implicacion": "Reactivar, sustituir o depurar el catálogo.",
                   "cautela": "Una existencia en cero puede estar en reposición."}}


def ejecutar(datos: Path = PROCESSED) -> dict:
    cifras = json.loads((datos / "preguntas_resumen.json").read_text(encoding="utf-8"))
    cifras_json = json.dumps(cifras, ensure_ascii=False, sort_keys=True)
    clave = hashlib.sha256(f"{VERSION}|{cifras_json}".encode()).hexdigest()[:24]
    salida = datos / "narrativa.json"
    previo = _previa(salida)
    if previo.get("clave") == clave and previo.get("origen") == "gemini":
        log.info("Narrativa en caché (cifras sin cambios).")
        previo = _fijar(previo, cifras)
        salida.write_text(json.dumps(previo, ensure_ascii=False, indent=2), encoding="utf-8")
        return previo

    origen, modelo, revisar = "plantilla", None, {}
    textos = plantilla(cifras)
    try:
        cli = ClienteGemini(pausa=0, timeout=60, reintentos=1, max_modelos=2)   # si no responde, plantilla
        preguntas = "\n".join(f"{k}: {v}" for k, v in PREGUNTAS.items())
        r = cli.json(PROMPT.format(preguntas=preguntas, cifras=cifras_json), ESQUEMA)
        for it in r.get("preguntas", []):
            if it.get("id") in PREGUNTAS:
                textos[it["id"]] = {k: it[k] for k in ("titular", "hallazgo", "implicacion", "cautela")}
                extra = _validar(it, cifras_json)
                if extra:
                    revisar[it["id"]] = extra
        origen, modelo = "gemini", cli.modelo
    except ErrorIA as e:
        log.warning("Gemini no disponible, se usa la plantilla: %s", e)

    out = {"clave": clave, "origen": origen, "modelo": modelo, "periodo": cifras.get("periodo"),
           "preguntas": {k: {"pregunta": PREGUNTAS[k], **textos[k]} for k in PREGUNTAS},
           "cifras_a_revisar": revisar}
    out = _fijar(out, cifras)
    salida.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description="Redacción de hallazgos con IA generativa")
    ap.add_argument("--datos", type=Path, default=PROCESSED)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    r = ejecutar(a.datos)
    print(json.dumps({"origen": r["origen"], "modelo": r["modelo"], "cifras_a_revisar": r["cifras_a_revisar"],
                      "titulares": {k: v["titular"] for k, v in r["preguntas"].items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
