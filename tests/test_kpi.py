"""Pruebas de los indicadores y de la regla de redistribución."""
import pandas as pd

from pipeline.kpi import _consumo, _racha_ceros, redistribucion


def test_consumo_aparente_ignora_reposiciones():
    # baja 100, baja 100, repone +500, baja 120 → mediana de las caídas = 100
    assert _consumo(pd.Series([1000, 900, 800, 1300, 1180])) == 100


def test_racha_de_meses_en_cero():
    assert _racha_ceros(pd.Series([5, 0, 3, 0, 0, 0])) == 3
    assert _racha_ceros(pd.Series([0, 0, 4])) == 0


def test_redistribucion_lleva_el_deficit_a_dos_meses_sin_dejar_al_origen_bajo_dos():
    r = pd.DataFrame([{
        "codigo": "1", "descripcion": "X", "critico": True, "nivel_riesgo": "alto", "precio_ultimo": 2.0,
        "existencia_CDPA": 1000, "consumo_CDPA": 100,     # 10 meses → puede ceder hasta quedar en 2
        "existencia_CDDI": 10, "consumo_CDDI": 50,        # 0.2 meses → necesita 90 para llegar a 2
        "existencia_CDCH": 150, "consumo_CDCH": 100,      # 1.5 meses → ni cede ni recibe
    }])
    t = redistribucion(r)
    assert len(t) == 1
    fila = t.iloc[0]
    assert (fila["desde"], fila["hacia"], fila["cantidad"]) == ("CDPA", "CDDI", 90)
    assert fila["cobertura_destino_despues"] == 2.0 and fila["valor"] == 180.0


def test_narrativa_detecta_cifras_inventadas():
    from pipeline.narrativa import _validar
    cifras = '{"P1": {"cambio_valor_pct": -64.3, "valor": 42.9}}'
    ok = {"titular": "El inventario cayó 64.3 % en 2025", "hallazgo": "Hoy vale B/. 42.9 M.", "implicacion": "", "cautela": ""}
    malo = {"titular": "El inventario cayó 71 %", "hallazgo": "", "implicacion": "", "cautela": ""}
    assert _validar(ok, cifras) == []
    assert _validar(malo, cifras) == ["71"]
