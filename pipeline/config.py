"""Configuración común del pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# Portal de Datos Abiertos de Panamá (CKAN)
CKAN_API = "https://www.datosabiertos.gob.pa/api/3/action"
CSS_ORG = "caja-de-seguro-social"

# openFDA — Drug Shortages (pública, sin clave)
OPENFDA_SHORTAGES = "https://api.fda.gov/drug/shortages.json"

# Centros de distribución de la CSS
CENTROS = {
    "CDPA": "Centro de Distribución de Panamá",
    "CDDI": "Centro de Distribución de Divisa",
    "CDCH": "Centro de Distribución de Chiriquí",
}
