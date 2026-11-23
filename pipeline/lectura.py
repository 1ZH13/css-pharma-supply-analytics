"""Lectura robusta de los CSV de la CSS.

Los archivos publicados entre 2021 y 2026 no comparten formato: cambian la
codificación (Windows-1252 o DOS CP850), el separador (`;` o `,`), la presencia
de encabezados, el número de filas de encabezado y la forma de escribir números
y códigos. Este módulo resuelve esas diferencias para que la transformación
trabaje siempre con filas de texto limpias.
"""
from __future__ import annotations

import csv
import io
import re
import statistics
import unicodedata
from pathlib import Path

MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
}
_ABREV = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
          "AGO": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DIC": 12}
_TRIM = {"I": 1, "1ER": 1, "II": 2, "2DO": 2, "III": 3, "3ER": 3, "IV": 4, "4TO": 4}

# Bytes que delatan cada codificación (vocales acentuadas y Ñ más frecuentes).
_BYTES_DOS = set(b"\xa2\xe0\xb5\x90\xa1\xa0\xd6")
_BYTES_WIN = set(b"\xf3\xd3\xcd\xc1\xe1\xed\xda\xc9\xd1\xf1\xfa")

# Código de producto: 9 dígitos (101000801) o con guiones (1-01-0008-01).
RE_CODIGO = re.compile(r"^\s*(\d{9}|\d-\d{2}-\d{4}-\d{2})\s*$")
RE_ATC = re.compile(r"^[A-Z]\d{2}[A-Z]{2}\d{2,5}$")


# ---------------------------------------------------------------- archivos
def detectar_codificacion(datos: bytes) -> str:
    """CP850 si predominan los bytes típicos de DOS; si no, Windows-1252."""
    dos = sum(1 for b in datos if b in _BYTES_DOS)
    win = sum(1 for b in datos if b in _BYTES_WIN)
    return "cp850" if dos > win else "cp1252"


def detectar_separador(texto: str) -> str:
    """`;` si la mediana de `;` por línea es 3 o más (las descripciones llevan comas)."""
    lineas = [l for l in texto.splitlines() if l.strip()][:80]
    if not lineas:
        return ","
    return ";" if statistics.median(l.count(";") for l in lineas) >= 3 else ","


def leer_filas(ruta: Path) -> tuple[list[list[str]], dict]:
    """Devuelve las filas del CSV ya decodificadas y la información de lectura."""
    datos = Path(ruta).read_bytes()
    if datos.startswith(b"\xef\xbb\xbf"):
        texto, cod = datos[3:].decode("utf-8", "replace"), "utf-8-sig"
    else:
        try:
            texto, cod = datos.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            cod = detectar_codificacion(datos)
            texto = datos.decode(cod, "replace")
    sep = detectar_separador(texto)
    filas = list(csv.reader(io.StringIO(texto), delimiter=sep))
    return filas, {"codificacion": cod, "separador": sep}


# ----------------------------------------------------------------- valores
def limpiar_texto(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalizar_codigo(s: str) -> str | None:
    """`1-01-0008-01` y `101000801` son el mismo producto: se guarda en 9 dígitos."""
    if not s or not RE_CODIGO.match(s):
        return None
    return re.sub(r"\D", "", s)


def codigo_con_guiones(c9: str) -> str:
    return f"{c9[0]}-{c9[1:3]}-{c9[3:7]}-{c9[7:9]}"


def numero(s: str | None) -> float | None:
    """Convierte `12,440,000`, `B/.0.54`, `871,890.00`, `0,05` o `3142.8` a número.

    Devuelve None si la celda está vacía o no es numérica.
    """
    if s is None:
        return None
    t = limpiar_texto(s).upper().replace("B/.", "").replace("B/", "").replace("$", "").replace(" ", "")
    if t in ("", "-", "--", "N/A", "NA", "S/E"):
        return None
    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+", t) else t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if negativo else v


def es_numero(s: str | None) -> bool:
    return numero(s) is not None


# ----------------------------------------------------------------- períodos
def mes_en_texto(s: str) -> int | None:
    t = sin_acentos(limpiar_texto(s).upper())
    for nombre, n in MESES.items():
        if re.search(rf"\b{nombre}\b", t):
            return n
    return None


def anio_en_texto(s: str) -> int | None:
    m = re.findall(r"20\d{2}", s)
    return int(m[-1]) if m else None


def periodos_de_archivo(nombre: str) -> list[str]:
    """Meses (AAAA-MM) que cubre un archivo según su nombre.

    `inventario-de-medicamentos-i-trim-2025.csv`   -> 2025-01..2025-03
    `inventario-de-medicamentos-mayo-a-septiembre-2024.csv` -> 2024-05..2024-09
    `cuadro-de-inventario-de-medicamentos-dic.-2023.csv`    -> 2023-12
    """
    t = sin_acentos(Path(nombre).stem.upper()).replace(".", "")
    anio = anio_en_texto(t)
    if anio is None:
        return []
    partes = t.split("-")
    if "TRIM" in partes:
        q = _TRIM.get(partes[partes.index("TRIM") - 1])
        if q:
            return [f"{anio}-{m:02d}" for m in range(3 * q - 2, 3 * q + 1)]

    def mes(p):
        return MESES.get(p) or _ABREV.get(p)

    meses = [mes(p) for p in partes if mes(p)]
    if "A" in partes and len(meses) >= 2:
        return [f"{anio}-{m:02d}" for m in range(meses[0], meses[-1] + 1)]
    return [f"{anio}-{meses[-1]:02d}"] if meses else []


def meses_hasta(fin: str, n: int) -> list[str]:
    """Los `n` meses consecutivos que terminan en `fin` (AAAA-MM)."""
    a, m = map(int, fin.split("-"))
    total = a * 12 + m - 1
    return [f"{(total - i) // 12}-{(total - i) % 12 + 1:02d}" for i in range(n - 1, -1, -1)]


def principio_activo(descripcion: str) -> str:
    """Nombre del principio activo: el texto antes de la primera cifra o coma."""
    t = sin_acentos(limpiar_texto(descripcion).upper())
    t = re.split(r"[\d,(]", t, maxsplit=1)[0]
    return limpiar_texto(t.strip(" .-/"))
