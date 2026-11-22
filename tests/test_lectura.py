"""Pruebas de las reglas de limpieza (python -m pytest)."""
import pytest

from pipeline.lectura import (
    detectar_codificacion, detectar_separador, meses_hasta, normalizar_codigo, numero,
    periodos_de_archivo, principio_activo,
)


@pytest.mark.parametrize("texto, esperado", [
    ("12,440,000", 12440000), ("B/.0.54", 0.54), (" B/.0.01 ", 0.01), ("871,890.00", 871890.0),
    ("0,05", 0.05), ("3142.8", 3142.8), ("", None), ("-", None), ("2,973,000 ", 2973000),
])
def test_numero(texto, esperado):
    assert numero(texto) == esperado


def test_codigos_viejo_y_nuevo_son_el_mismo():
    assert normalizar_codigo("1-01-0008-01") == normalizar_codigo("101000801") == "101000801"
    assert normalizar_codigo("CODIGO") is None


@pytest.mark.parametrize("nombre, esperado", [
    ("inventario-de-medicamentos-i-trim-2025.csv", ["2025-01", "2025-02", "2025-03"]),
    ("inventario-de-medicamentos-4to-trim-2025.csv", ["2025-10", "2025-11", "2025-12"]),
    ("cuadro-de-medicamentos-iii-trim-2026.csv", ["2026-07", "2026-08", "2026-09"]),
    ("cuadro-de-inventario-de-medicamentos-dic.-2023.csv", ["2023-12"]),
    ("inventario-de-medicamentos-mayo-a-septiembre-2024.csv", [f"2024-{m:02d}" for m in range(5, 10)]),
    ("invetario-de-medicamentos-agosto-2022.csv", ["2022-08"]),
])
def test_periodos_de_archivo(nombre, esperado):
    assert periodos_de_archivo(nombre) == esperado


def test_meses_hasta_cruza_el_anio():
    assert meses_hasta("2024-01", 3) == ["2023-11", "2023-12", "2024-01"]


def test_codificacion_y_separador():
    assert detectar_codificacion("DESCRIPCIÓN".encode("cp850")) == "cp850"
    assert detectar_codificacion("DESCRIPCIÓN".encode("cp1252")) == "cp1252"
    assert detectar_separador('101000801;GLIBENCLAMIDA, 5MG, TABLETA, V.O;0.03;26,361,000;2,078,000\n' * 5) == ";"
    assert detectar_separador('101000801,"GLIBENCLAMIDA, 5MG",0.03,"14,938,000"\n' * 5) == ","


def test_principio_activo():
    assert principio_activo("GLIBENCLAMIDA, 5MG, TABLETA, V.O") == "GLIBENCLAMIDA"
    assert principio_activo("LIDOCAÍNA CLORHIDRATO 2% con EPINEFRINA") == "LIDOCAINA CLORHIDRATO"
