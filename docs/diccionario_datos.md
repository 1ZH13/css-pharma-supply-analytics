# Diccionario de datos

Tablas que produce `python -m pipeline.transform` en `data/processed/` (CSV en UTF-8 con BOM, listos para Power BI y Excel). Las mismas tablas se cargan en MongoDB Atlas, base `css_pharma`, con `python -m pipeline.load`.

## `existencias` — hecho principal

Una fila por **medicamento × mes × centro de distribución**.

| Campo | Tipo | Descripción |
|---|---|---|
| `periodo` | texto `AAAA-MM` | Mes del corte de inventario |
| `anio`, `mes` | entero | Año y mes, separados para filtrar |
| `codigo` | texto (9 dígitos) | Código CSS unificado. `1-01-0008-01` (formato desde 2025) = `101000801` |
| `centro` | texto | `CDPA` Panamá · `CDDI` Divisa · `CDCH` Chiriquí |
| `cantidad` | número | Existencia disponible en el almacén al cierre del mes (unidades de despacho) |
| `precio_unitario` | número (B/.) | Precio efectivo: monto publicado ÷ cantidad total; si no hay monto, el precio publicado |
| `valor` | número (B/.) | `cantidad × precio_unitario` |
| `precio_imputado` | booleano | `true` si el archivo del mes no traía precio (ene–jul 2021) y se tomó el del mes más cercano |
| `atipico` | booleano | `true` si el total del mes supera 20 veces la mediana del medicamento. **Excluir de los KPI** |
| `archivo` | texto | CSV de origen (trazabilidad) |

## `medicamentos` — catálogo

| Campo | Descripción |
|---|---|
| `codigo`, `codigo_guiones` | Código en 9 dígitos y en el formato con guiones de 2025 |
| `descripcion` | Nombre, concentración, forma y vía, según la publicación más reciente |
| `principio_activo` | Texto antes de la primera cifra o coma, sin tildes (para cruzar con openFDA y noticias) |
| `atc` | Código SAFIRO de la CSS, basado en la clasificación ATC de la OMS (p. ej. `A10BB00001`) |
| `atc_nivel1`, `grupo_terapeutico` | Primer nivel ATC y su nombre (p. ej. `A` Tracto alimentario y metabolismo) |
| `categoria_critica`, `critico` | Grupo de tratamiento continuo o de alto impacto (insulinas, oncológicos, VIH, cardiovascular…). **Propuesta para validar con la Dirección Nacional de Farmacia** |
| `tipo_compra` | Modalidad de compra (solo 2021–2022) |
| `precio_ultimo` | Precio efectivo del último mes con dato |
| `primer_periodo`, `ultimo_periodo`, `meses_con_dato` | Presencia del renglón en la serie |

## `equivalencias_codigos`

Cada código tal como aparece en la fuente → código unificado, con el formato (`9 dígitos` / `con guiones`) y el rango de meses en que se usó. El cambio de 2025 es solo de formato: el número es el mismo.

## `totales_referencia`

Totales nacionales mensuales que la CSS publica en sus *cuadros comparativos* (2020–2024). Se usan para validar la lectura (ver `reporte_calidad.md`) y como única fuente para 2020, que no tiene detalle por centro.

## `fda_escasez` — openFDA Drug Shortages (JSON)

| Campo | Descripción |
|---|---|
| `generic_name`, `sustancia` | Nombre genérico y sustancia activa (inglés) |
| `status` | `Current`, `Resolved`, `To Be Discontinued` |
| `availability` | Disponibilidad de la presentación |
| `categoria_terapeutica`, `forma`, `presentacion`, `empresa` | Detalle de la presentación |
| `motivo` | Causa de la escasez reportada por el fabricante |
| `fecha_inicio`, `fecha_actualizacion`, `fecha_descontinuacion` | Fechas en `AAAA-MM-DD` |

En MongoDB se guarda el documento JSON original de openFDA (con el subdocumento `openfda`).

## `documentos` — texto no estructurado (`documentos.jsonl`)

Noticias e informes sobre desabastecimiento: metadatos de `fuentes_texto.csv` + `texto` extraído (HTML o PDF), `caracteres` y `estado` (`ok`, `incompleto`, `sin_descarga`). Es la entrada de la Etapa 3 (IA generativa).

## IA generativa (Etapa 3) — `python -m pipeline.ia_texto`

Gemini lee cada noticia o informe y devuelve JSON con un esquema fijo (`pipeline/ia_texto.py`). Las respuestas se guardan en `ia_cache.json` por hash del texto: cada ejecución solo envía a Gemini lo nuevo.

| Tabla | Grano | Campos principales |
|---|---|---|
| `ia_documentos.jsonl` | documento | `resumen`, `fecha_evento`, `tipo_evento` (desabastecimiento, compra_o_licitacion, mejora_abastecimiento, robo_o_perdida, queja_pacientes, politica_o_regulacion, informe_tecnico, otro), `causas`, `medicamentos` (nombre, principio activo, situación: faltante / abastecido / en_compra / mencionado), `grupos_afectados`, `instalaciones`, `cifras`, `nivel_abastecimiento_pct`, `medidas_anunciadas`, `tono`, `riesgo` (alto / medio / bajo), `modelo` |
| `ia_menciones.csv` | medicamento mencionado × código CSS | `documento`, `mencion`, `principio_activo_mencion`, `situacion`, `codigo`, `descripcion_css`, `coincidencia` (exacta / parcial / sin_coincidencia), `riesgo` |
| `ia_causas.csv` | documento × causa | `causa` (incumplimiento_proveedor, proceso_de_compra, presupuesto_o_pagos, robo_o_perdida, vencimiento, logistica_distribucion, demanda_creciente, escasez_global, gestion_institucional, otra) |
| `inn_equivalencias.csv` | principio activo | `principio_activo` (español, CSS) → `inn_en` (nombre genérico en inglés usado por la FDA) |
| `cruce_fda.csv` | medicamento CSS | `inn_en`, `registros_fda`, `registros_fda_vigentes`, `escasez_eeuu_vigente`, `motivos_fda`, `ultima_actualizacion_fda` |

## Trazabilidad

| Tabla | Contenido |
|---|---|
| `incidencias` | Cada problema de calidad detectado: tipo, archivo, código, mes y detalle |
| `lectura_archivos` | Cómo se leyó cada CSV: familia, codificación, separador, encabezado, filas |
| `calidad.json` / `reporte_calidad.md` | Indicadores de completitud, validez, unicidad y exactitud |
| `ejecuciones` (solo MongoDB) | Bitácora de cada carga: inicio, fin, documentos por colección y origen |
