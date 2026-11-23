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
notebooks/         demo_sig.ipynb: indicadores principales (se ejecuta en Colab)
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
                                #    (o: git fetch origin data && git checkout origin/data -- raw)
python -m pipeline.transform    # 2. limpia y unifica → data/processed/
python -m pipeline.quality      # 3. reporte de calidad → data/processed/reporte_calidad.md
python -m pipeline.ia_texto     # 4. IA generativa sobre noticias (requiere GEMINI_API_KEY en .env)
python -m pipeline.kpi          # 5. KPI, riesgo y redistribución
python -m pipeline.preguntas    # 6. las 6 preguntas del proyecto
python -m pipeline.narrativa    # 7. hallazgos redactados por IA
python -m pipeline.load         # 8. carga en MongoDB Atlas (requiere MONGODB_URI en .env)
python -m pytest -q tests       #    pruebas de las reglas de limpieza
```

Las tablas limpias también se publican automáticamente en la carpeta `processed/` de la rama `data`, listas para Power BI.

## Las 6 preguntas y el dashboard

| # | Pregunta | Decisión que habilita |
|---|---|---|
| 1 | ¿Qué pasó con el inventario de la CSS en 2025? | ¿Inventario ajustado por política o riesgo a corregir? (con el dinero inmovilizado como apoyo) |
| 2 | ¿Es real el "90 % de abastecimiento" que anuncia la CSS? | Con qué indicador rendir cuentas |
| 3 | ¿Quiénes pagan el desabastecimiento? | Priorizar compras y stock de seguridad por grupo de pacientes |
| 4 | ¿El interior del país está peor abastecido? | Órdenes de traslado entre CDPA, CDDI y CDCH |
| 5 | ¿Funcionó la Comisión de Desabastecimiento Crítico? | Mantener o ampliar la compra conjunta |
| 6 | ¿Cuáles son los medicamentos "fantasma"? | Reactivar, sustituir o depurar el catálogo |

`python -m pipeline.preguntas` calcula las tablas de cada pregunta y `python -m pipeline.narrativa` hace que **Gemini redacte el titular y la interpretación usando solo las cifras calculadas** (cada número del texto se valida contra los datos).

**Dashboard (Streamlit):** una página por pregunta + el asistente **"Pregúntale a los datos"** (Gemini responde con las tablas del sistema).

```bash
streamlit run dashboard/streamlit/app.py
```

Lee de MongoDB Atlas si encuentra `MONGODB_URI` (en `.streamlit/secrets.toml` o en el entorno); si no, usa las tablas publicadas en la rama `data`. El asistente necesita `GEMINI_API_KEY`.

Publicado en **https://css-medicamentos-panama.streamlit.app**.

**Dashboard (Power BI):** el reporte `dashboard/powerbi/CSS_inventario_medicamentos.pbip` tiene 7 páginas: resumen y una por pregunta. Lee la rama `data` y no necesita credenciales. Ver [`dashboard/powerbi/README.md`](dashboard/powerbi/README.md).

**Notebook de demostración:** [`notebooks/demo_sig.ipynb`](notebooks/demo_sig.ipynb) reproduce los KPI, el riesgo, los traslados y los fantasmas. Lee de MongoDB si existe `MONGODB_URI`; si no, de la rama `data`. [Abrir en Colab](https://colab.research.google.com/github/1ZH13/css-pharma-supply-analytics/blob/main/notebooks/demo_sig.ipynb).

**Recomendaciones, riesgos y limitaciones (Etapa 6):** ver [`docs/recomendaciones.md`](docs/recomendaciones.md).

## Limpieza y unificación (Etapa 2)

Los 79 CSV de la CSS (2021–2026) no comparten formato. El pipeline resuelve:

| Problema en la fuente | Tratamiento |
|---|---|
| Codificación Windows-1252 o DOS (CP850) según el archivo | Detección por los bytes de las vocales acentuadas |
| Separador `;` o `,` (y comas dentro de las descripciones) | Mediana de `;` por línea |
| Archivos sin encabezado, con 1 o 2 filas de encabezado | Lectura por posición validada con la suma de centros |
| Un mes por archivo, trimestres o varios meses en columnas | Bloques por mes (CDPA, CDDI, CDCH, total, monto) |
| Plantillas trimestrales con bloques vacíos o repetidos | Por cada mes se toma el bloque con datos |
| Códigos `101000801` y `1-01-0008-01` (desde 2025) | Mismo código: se unifica en 9 dígitos |
| Números como texto: `12,440,000`, `B/.0.54`, `0,05` | Conversión con reglas para miles y decimales |
| Precio publicado redondeado (0.03 vs 0.0271) | Precio efectivo = monto ÷ cantidad |
| Meses repetidos en dos archivos | Se conserva el archivo más reciente |
| Cantidades fuera de escala (agosto 2024) | Se marcan como `atipico` y se excluyen de los KPI |

Resultado: **109 893 filas** (673 medicamentos × 67 meses × 3 centros). Los totales calculados coinciden en un **99.95–100 %** con los que la propia CSS publica en sus cuadros comparativos. Detalle en [`docs/reporte_calidad.md`](docs/reporte_calidad.md) y [`docs/diccionario_datos.md`](docs/diccionario_datos.md).

## IA generativa (Etapa 3)

Las noticias e informes sobre desabastecimiento (21 fuentes: La Prensa, La Estrella, TVN, Telemetro, Panamá América, MINSA, Instituto Gorgas, OPS) se procesan con **Google Gemini** (modelo Flash; se elige automáticamente el más reciente disponible):

1. **Extracción estructurada**: Gemini devuelve JSON con un esquema fijo (tipo de evento, causas, medicamentos y su situación, grupos de pacientes, instalaciones, cifras, tono y riesgo). Se le pide no inventar: solo lo que dice el texto.
2. **Cruce con el inventario**: cada medicamento mencionado se enlaza con los códigos CSS por principio activo, para comparar lo que reporta la prensa con las existencias reales.
3. **Cruce internacional**: Gemini traduce los principios activos al nombre genérico en inglés (GLIBENCLAMIDA → glyburide) y se cruzan con openFDA para saber qué medicamentos de la CSS también están en escasez en EE. UU. (causa de proveedor global frente a problema local).

Las respuestas se guardan en caché por hash del texto, así cada ejecución mensual solo consulta lo nuevo y se mantiene dentro de la capa gratuita.

## Flujo de trabajo y ramas

| Rama | Propósito |
|---|---|
| `main` | Versión estable y entregable. Solo recibe cambios desde `qa` por pull request. |
| `qa` | Pruebas: se valida el pipeline completo y la demo antes de pasar a `main`. |
| `develop` | Integración del trabajo terminado. |
| `feature/<tarea>` | Una rama corta por tarea; se integra a `develop` por pull request. |
| `hotfix/<arreglo>` | Soporte: corrige algo urgente desde `main` y vuelve a `main` y `develop`. |
| `data` | Datos crudos de fuentes abiertas (`raw/`) y tablas limpias (`processed/`), escrita solo por GitHub Actions. No incluye textos de noticias. Nunca se mezcla. |

Automatización (GitHub Actions):
- **Extracción de fuentes** (`extract.yml`): el día 3 de cada mes, a mano o al cambiar el extractor; descarga las fuentes y las versiona en la rama `data`.
- **Pipeline de datos** (`pipeline.yml`): después de cada extracción (y a mano) limpia, transforma, genera el reporte de calidad, publica las tablas en `data/processed/` y las carga en MongoDB Atlas (secreto `MONGODB_URI`).
- **Verificación** (`ci.yml`): en cada pull request corre las pruebas y el pipeline completo sobre los datos reales.

Commits con prefijo: `feat:`, `fix:`, `data:`, `docs:`, `ci:`.

## Fuentes y licencias

- **Caja de Seguro Social — Inventario de medicamentos**, Portal de Datos Abiertos de Panamá. Licencia Creative Commons Attribution (CC BY).
- **openFDA — Drug Shortages**, U.S. Food and Drug Administration. Datos públicos.
- Noticias e informes: se usan solo para análisis, citando la fuente y su enlace. **El texto completo no se publica en el repositorio**: el pipeline lo descarga en cada ejecución dentro del runner de GitHub Actions, lo analiza con IA y lo guarda solo en MongoDB Atlas (base privada). En la rama `data` quedan únicamente los metadatos (URL, fecha, tamaño, hash) y el análisis de la IA.

Detalle en [`docs/fuentes.md`](docs/fuentes.md).

**Licencia del código:** MIT (ver [`LICENSE`](LICENSE)). La licencia MIT cubre el código del repositorio. Los datos publicados en la rama `data` conservan la licencia de su fuente: CC BY para los de la CSS, con atribución a la Caja de Seguro Social. El análisis de las noticias se publica para fines académicos, con enlace a cada medio.

## Equipo

| Rol | Integrante |
|---|---|
| Director(a) de Tecnología e Información (líder) | _por definir_ |
| Ingeniero(a) de Datos | _por definir_ |
| Analista de BI | _por definir_ |
| Director(a) Nacional de Farmacia | _por definir_ |
| Gerente de Logística y Cadena de Suministro | _por definir_ |
| Gerente de Calidad y Atención al Asegurado | _por definir_ |
