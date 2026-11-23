"""Los titulares de P2 y P5 usan siempre las mismas cifras que el documento y Power BI."""
from pipeline.narrativa import titulares_fijos

CIFRAS = {
    "P2": {"pct_declarado_min": 90.0, "pct_declarado_max": 96.0, "pct_datos_12m_min": 78.8, "pct_datos_12m_max": 86.3},
    "P5": {"hito": "2025-10", "abastecimiento_en_hito_pct": 78.8, "abastecimiento_ultimo_pct": 86.3},
}


def test_titular_p2():
    assert titulares_fijos(CIFRAS)["P2"] == "Se anuncian 90–96 % de abastecimiento; los datos muestran 78.8–86.3 %"


def test_titular_p5():
    assert titulares_fijos(CIFRAS)["P5"] == "Desde la Comisión (oct-2025) el abastecimiento subió de 78.8 % a 86.3 %"
