# CSS Pharma Supply Analytics

**Sistema de Información Gerencial para anticipar el desabastecimiento de medicamentos en la Caja de Seguro Social (CSS) de Panamá.**

Integra los inventarios públicos de la CSS (2021–2026), registros internacionales de escasez (openFDA) y noticias sobre desabastecimiento analizadas con IA generativa, para responder una pregunta gerencial:

> **¿Qué medicamentos están en riesgo de desabastecimiento y cómo redistribuir el inventario entre los centros de distribución de Panamá, Divisa y Chiriquí?**

Proyecto final — Sistemas de Información Gerencial, Universidad Tecnológica de Panamá (2026).

---

## Arquitectura

```
Fuentes                     Pipeline (Python)                   Almacenamiento     Consumo
─────────────────────────   ─────────────────────────────────   ───────────────    ─────────────────
CSS · CSV (datosabiertos) ─┐
openFDA · JSON (API)      ─┼─► extraer → limpiar → unificar ─► MongoDB Atlas ─┬─► Streamlit (demo)
Noticias · texto (web)    ─┘    → IA generativa (texto)                       └─► Power BI
                                  ▲
                    GitHub Actions (ejecución programada)
```

| Tipo de dato | Fuente | Formato | Uso |
|---|---|---|---|
| Estructurado | Inventario de medicamentos — CSS, Dirección Nacional de Logística | CSV / XLSX | Existencias mensuales por centro de distribución, precio y valor |
| Semiestructurado | openFDA Drug Shortages | JSON (API REST) | Referencia internacional de escasez por principio activo |
| No estructurado | Noticias e informes sobre desabastecimiento | HTML / PDF → texto | IA generativa extrae medicamento, causa y fecha |

## Estructura del repositorio

```
data/raw/          Datos crudos descargados (no versionados; se regeneran)
data/processed/    Datos limpios y unificados
pipeline/          Extracción, limpieza, transformación y carga
notebooks/         Exploración y análisis
dashboard/         Streamlit y Power BI
docs/              Fuentes, diccionario de datos y decisiones de diseño
```

## Cómo ejecutarlo

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # y completar las credenciales

python -m pipeline.extract      # 1. descarga las fuentes a data/raw/
                                # (o usar los datos ya descargados de la rama `data`)
```

Las siguientes etapas (limpieza, carga en MongoDB, IA y dashboards) se documentan a medida que se incorporan.

## Flujo de trabajo y ramas

| Rama | Propósito |
|---|---|
| `main` | Versión estable y entregable. Solo recibe cambios desde `qa` por pull request. |
| `qa` | Pruebas: se valida el pipeline completo y la demo antes de pasar a `main`. |
| `develop` | Integración del trabajo terminado. |
| `feature/<tarea>` | Una rama corta por tarea; se integra a `develop` por pull request. |
| `hotfix/<arreglo>` | Soporte: corrige algo urgente desde `main` y vuelve a `main` y `develop`. |
| `data` | Solo datos crudos, escrita por GitHub Actions. Nunca se mezcla. |

Automatización (GitHub Actions):
- **Extracción de fuentes** (`extract.yml`): el día 3 de cada mes, a mano o al cambiar el extractor; descarga las fuentes y las versiona en la rama `data`.
- **Verificación** (`ci.yml`): en cada pull request comprueba que el pipeline compile y se ejecute.

Commits con prefijo: `feat:`, `fix:`, `data:`, `docs:`, `ci:`.

## Fuentes y licencias

- **Caja de Seguro Social — Inventario de medicamentos**, Portal de Datos Abiertos de Panamá. Licencia Creative Commons Attribution (CC BY).
- **openFDA — Drug Shortages**, U.S. Food and Drug Administration. Datos públicos.
- Noticias e informes: se usan solo para análisis, citando la fuente; el texto completo no se redistribuye en el repositorio.

Detalle en [`docs/fuentes.md`](docs/fuentes.md).

## Equipo

| Rol | Integrante |
|---|---|
| Director(a) de Tecnología e Información (líder) | _por definir_ |
| Ingeniero(a) de Datos | _por definir_ |
| Analista de BI | _por definir_ |
| Director(a) Nacional de Farmacia | _por definir_ |
| Gerente de Logística y Cadena de Suministro | _por definir_ |
| Gerente de Calidad y Atención al Asegurado | _por definir_ |
