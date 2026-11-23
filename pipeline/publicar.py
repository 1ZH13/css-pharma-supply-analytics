"""Publica las tablas limpias en la rama `data` sin redistribuir textos de terceros.

Las noticias pertenecen a sus medios: el repositorio es público, así que en `data/processed`
solo se publican los metadatos de cada documento (fuente, título, URL, fecha, tamaño, estado)
y el análisis de la IA, nunca el texto completo. El texto se descarga en cada ejecución,
se usa dentro del runner y se guarda solo en MongoDB Atlas (base privada).

Uso:  python -m pipeline.publicar --origen data/processed --destino _data/processed
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

CAMPOS_PRIVADOS = {"texto"}
ARCHIVOS_CON_TEXTO = {"documentos.jsonl"}


def publicar(origen: Path, destino: Path) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.iterdir():
        if viejo.is_file() and viejo.name != ".gitkeep" and not (origen / viejo.name).exists():
            viejo.unlink()
    n = {"copiados": 0, "sin_texto": 0}
    for f in sorted(origen.iterdir()):
        if not f.is_file() or f.name == ".gitkeep":
            continue
        if f.name in ARCHIVOS_CON_TEXTO:
            lineas = []
            for l in f.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    d = json.loads(l)
                    for c in CAMPOS_PRIVADOS:
                        d.pop(c, None)
                    lineas.append(json.dumps(d, ensure_ascii=False))
            (destino / f.name).write_text("\n".join(lineas) + "\n", encoding="utf-8")
            n["sin_texto"] += 1
        else:
            shutil.copy2(f, destino / f.name)
        n["copiados"] += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--origen", type=Path, required=True)
    ap.add_argument("--destino", type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(publicar(a.origen, a.destino), ensure_ascii=False))


if __name__ == "__main__":
    main()
