# Rama `data` — datos crudos

Rama **solo de datos**. La escribe únicamente el flujo automático
[`extract.yml`](../../blob/main/.github/workflows/extract.yml) de GitHub Actions; **nunca se mezcla** con `main`, `qa` ni `develop`.

```
raw/css/        Inventarios de medicamentos de la Caja de Seguro Social (CSV, datosabiertos.gob.pa, CC BY)
raw/openfda/    Registros de escasez de medicamentos de openFDA (JSON)
raw/texto/      Noticias e informes sobre desabastecimiento (texto plano)
```

Cada carpeta incluye `_manifest.json` con la URL de origen, la fecha de descarga, el tamaño y el hash SHA-256 de cada archivo.

Para usar estos datos en una copia local del proyecto:

```bash
git fetch origin data
git worktree add ../css-pharma-data origin/data
```
