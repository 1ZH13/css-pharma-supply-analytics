"""Pruebas de la Etapa 3 sin conexión: Gemini se reemplaza por un cliente simulado."""
import pandas as pd

import pipeline.ia_texto as T
from pipeline.ia import candidatos

CATALOGO = pd.DataFrame({
    "codigo": ["101000801", "101030001", "102050001", "102050002"],
    "descripcion": ["GLIBENCLAMIDA, 5MG, TABLETA", "AMLODIPINA 5mg, tableta", "INSULINA NPH 100 UI/mL",
                    "INSULINA GLARGINA 100 UI/mL"],
    "principio_activo": ["GLIBENCLAMIDA", "AMLODIPINA", "INSULINA NPH", "INSULINA GLARGINA"],
})


def test_menciones_se_enlazan_con_el_catalogo():
    analisis = [{"id": "n01", "tipo_evento": "desabastecimiento", "riesgo": "alto",
                 "medicamentos": [{"nombre": "insulina", "principio_activo": "Insulina", "situacion": "faltante"},
                                  {"nombre": "amlodipino", "principio_activo": "AMLODIPINA", "situacion": "en_compra"},
                                  {"nombre": "x", "principio_activo": "MEDICAMENTO INEXISTENTE", "situacion": "faltante"}]}]
    m = T.menciones(analisis, CATALOGO)
    assert set(m.loc[m["principio_activo_mencion"] == "INSULINA", "codigo"]) == {"102050001", "102050002"}
    assert m.loc[m["principio_activo_mencion"] == "AMLODIPINA", "coincidencia"].iloc[0] == "exacta"
    assert m.loc[m["principio_activo_mencion"] == "MEDICAMENTO INEXISTENTE", "codigo"].isna().all()


def test_cruce_fda_por_nombre_en_ingles():
    inn = pd.DataFrame({"principio_activo": ["GLIBENCLAMIDA", "AMLODIPINA"], "inn_en": ["glyburide", "amlodipine"]})
    fda = pd.DataFrame({"sustancia": ["GLYBURIDE", "AMLODIPINE BESYLATE"], "generic_name": ["Glyburide Tablets", "Amlodipine"],
                        "status": ["Current", "Resolved"], "motivo": ["Demand increase", None],
                        "fecha_actualizacion": ["2026-11-01", "2025-01-01"]})
    c = T.cruce_fda(CATALOGO, inn, fda).set_index("codigo")
    assert bool(c.loc["101000801", "escasez_eeuu_vigente"]) is True
    assert bool(c.loc["101030001", "escasez_eeuu_vigente"]) is False


def test_seleccion_de_modelo_prefiere_flash_estable_mas_reciente(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    c = candidatos(["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.6-flash-image", "gemini-flash-latest", "gemini-3-pro"])
    assert c[0] == "gemini-3.6-flash" and "gemini-3.6-flash-image" not in c and "gemini-3-pro" not in c
