# Reporte de calidad de datos — Inventario de medicamentos CSS

_Generado automáticamente por `pipeline/quality.py` el 2026-11-23._

## Resumen

| Indicador | Valor |
|---|---|
| Período cubierto | 2021-01 a 2026-09 |
| Meses con datos | 67 de 69 (97.1 %) |
| Meses sin publicación | 2024-11, 2024-12 |
| Archivos CSV leídos | 78 |
| Filas de existencias (medicamento × mes × centro) | 109,893 |
| Medicamentos distintos | 673 (promedio 546.7 por mes) |
| Medicamentos con código ATC | 87.4 % |
| Filas con precio imputado (ene–jul 2021) | 10.67 % |
| Unicidad (sin duplicados medicamento-mes-centro) | 100.0 % |
| Renglones-mes atípicos | 111 (0.303 %) |
| Registros openFDA | 1,581 |
| Documentos de texto con contenido útil | 15 de 21 |

## Exactitud: validación cruzada

Los totales nacionales calculados (suma de CDPA + CDDI + CDCH) se comparan con los que la CSS publica en sus *cuadros comparativos*.

| Año | Comparaciones | Coinciden |
|---|---|---|
| 2021 | 6,382 | 100.0 % |
| 2022 | 6,399 | 99.98 % |
| 2023 | 6,640 | 99.95 % |
| 2024 | 5,228 | 100.0 % |

## Incidencias detectadas y tratamiento

| Tipo | Casos | Tratamiento |
|---|---|---|
| `precio_publicado_redondeado` | 1,292 | La CSS publica el precio con 2 decimales pero calcula el monto con el precio completo. Se usa el precio efectivo (monto ÷ cantidad). |
| `cantidad_atipica` | 111 | Total del mes más de 20 veces la mediana del medicamento. Se marca `atipico = true` y se excluye de los KPI. |
| `sin_codigo_atc` | 85 | Medicamento sin código SAFIRO/ATC (no aparece en los cuadros comparativos). |
| `monto_no_cuadra` | 37 | El monto publicado no coincide con cantidad × precio (más de 1 %). Se conserva la cantidad; el valor se recalcula. |
| `codigo_con_varias_descripciones` | 35 | El mismo código aparece con nombres distintos (variantes de escritura o reutilización). |
| `sin_precio` | 9 | Ningún archivo informa precio para el medicamento. |
| `total_no_cuadra` | 7 | La suma de los tres centros no coincide con el total publicado. Se usa la suma de los centros. |
| `texto_sin_descarga` | 6 | La noticia o el informe no se pudo descargar. |
| `existencia_negativa` | 2 | Existencia menor que cero en la fuente. |
| `archivo_excluido` | 1 | Archivo fuera del alcance (insumos médico-quirúrgicos). |

### Meses con más renglones atípicos

- **2024-08**: 68 renglones
- **2021-04**: 5 renglones
- **2021-03**: 4 renglones
- **2021-08**: 3 renglones
- **2021-05**: 2 renglones

Agosto de 2024 concentra la mayoría: la publicación oficial (y su cuadro comparativo) trae cantidades decenas de veces superiores al resto del año. Se conservan, pero se excluyen de los indicadores.

## Formatos de origen

| Archivo | Familia | Codificación | Separador | Encabezado | Filas |
|---|---|---|---|---|---|
| css-inventario-medicamentos-abril-2021.csv | inventario | cp1252 | `;` | sí | 527 |
| css-inventario-medicamentos-enero-2021.csv | inventario | cp1252 | `;` | sí | 529 |
| css-inventario-medicamentos-febrero-2021.csv | inventario | cp1252 | `;` | sí | 529 |
| css-inventario-medicamentos-julio-2021.csv | inventario | cp1252 | `;` | sí | 538 |
| css-inventario-medicamentos-junio-2021.csv | inventario | cp1252 | `;` | sí | 528 |
| css-inventario-medicamentos-marzo-2021.csv | inventario | cp1252 | `;` | sí | 533 |
| css-inventario-medicamentos-mayo-2021.csv | inventario | cp1252 | `;` | sí | 528 |
| cuadro-ccomparativo-de-medicamentos-julio-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-existencias-de-enero-a-diciembre-ano-2021.csv | comparativo | nan | `nan` | — | 13,080 |
| cuadro-comparativo-de-existencias-de-enero-a-noviembre-ano-2021.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-existencias-enero-a-septiembre-ano-2021.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-abril-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-abril-2023.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-abril-2024.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-agosto-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-agosto-2023.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-de-marzo-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-dic.-2022.csv | comparativo | nan | `nan` | — | 6,624 |
| cuadro-comparativo-de-medicamentos-dic.-2023.csv | comparativo | nan | `nan` | — | 7,212 |
| cuadro-comparativo-de-medicamentos-enero-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-enero-2024.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-feb.-2024.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-febrero-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-junio-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-marzo-2024.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-mayo-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-mayo-a-septiembre-2024.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-nov.-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-nov.-2023.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-octubre-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-octubre-2023.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-octubre-2024.csv | comparativo | nan | `nan` | — | 6,631 |
| cuadro-comparativo-de-medicamentos-septiembre-2022.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comparativo-de-medicamentos-septiembre-2023.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-comporativo-de-existencias-medicamentos-enero-a-octubre-ano-2021.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-corporativo-de-medicamentos-de-mayo-junio-julio-2023.csv | comparativo | nan | `nan` | — | 0 |
| cuadro-de-inventario-de-medicamentos-abril-2023.csv | inventario | cp1252 | `;` | no | 588 |
| cuadro-de-inventario-de-medicamentos-agosto-2023.csv | inventario | cp1252 | `;` | no | 522 |
| cuadro-de-inventario-de-medicamentos-dic.-2023.csv | inventario | cp850 | `,` | sí | 512 |
| cuadro-de-inventario-de-medicamentos-enero-2023.csv | inventario | cp1252 | `;` | no | 600 |
| cuadro-de-inventario-de-medicamentos-feb.-2024.csv | inventario | cp1252 | `,` | no | 517 |
| cuadro-de-inventario-de-medicamentos-febrero-2023.csv | inventario | cp1252 | `;` | no | 594 |
| cuadro-de-inventario-de-medicamentos-julio-2023.csv | inventario | cp850 | `,` | sí | 581 |
| cuadro-de-inventario-de-medicamentos-junio-2023.csv | inventario | cp850 | `,` | sí | 581 |
| cuadro-de-inventario-de-medicamentos-marzo-2023.csv | inventario | cp1252 | `;` | no | 586 |
| cuadro-de-inventario-de-medicamentos-mayo-2023.csv | inventario | cp850 | `,` | sí | 581 |
| cuadro-de-inventario-de-medicamentos-nov.-2023.csv | inventario | cp1252 | `;` | no | 509 |
| cuadro-de-inventario-de-medicamentos-octubre-2023.csv | inventario | cp850 | `,` | sí | 509 |
| cuadro-de-inventario-de-medicamentos-septiembre-2023.csv | inventario | cp1252 | `;` | no | 503 |
| cuadro-de-medicamentos-diciembre-2021.csv | inventario | cp1252 | `;` | sí | 535 |
| cuadro-de-medicamentos-enero-2022.csv | inventario | cp1252 | `;` | sí | 532 |
| cuadro-de-medicamentos-iii-trim-2026.csv | inventario | cp850 | `,` | sí | 1,665 |
| cuadro-inventario-de-medicamentos-enero-2024.csv | inventario | cp1252 | `;` | sí | 512 |
| informe-de-medicamentos-ii-trim-2026.csv | inventario | cp1252 | `;` | sí | 1,662 |
| inventario-de-medicamentos-3er-trim-2025.csv | inventario | cp850 | `,` | sí | 1,749 |
| inventario-de-medicamentos-4to-trim-2025.csv | inventario | cp850 | `,` | sí | 1,758 |
| inventario-de-medicamentos-abril-2022.csv | inventario | cp1252 | `;` | no | 531 |
| inventario-de-medicamentos-abril-2024.csv | inventario | cp1252 | `;` | sí | 517 |
| inventario-de-medicamentos-de-mayo-2022.csv | inventario | cp1252 | `;` | no | 531 |
| inventario-de-medicamentos-dic.-2022.csv | inventario | cp1252 | `;` | no | 594 |
| inventario-de-medicamentos-febrero-2022.csv | inventario | cp1252 | `;` | sí | 532 |
| inventario-de-medicamentos-i-trim-2025.csv | inventario | cp850 | `,` | sí | 1,614 |
| inventario-de-medicamentos-i-trim-2026.csv | inventario | cp850 | `,` | sí | 1,668 |
| inventario-de-medicamentos-ii-trim-2025.csv | inventario | cp850 | `,` | sí | 1,614 |
| inventario-de-medicamentos-julio-2022.csv | inventario | cp1252 | `;` | no | 530 |
| inventario-de-medicamentos-marzo-2022.csv | inventario | cp1252 | `;` | sí | 532 |
| inventario-de-medicamentos-marzo-2024.csv | inventario | cp1252 | `;` | no | 518 |
| inventario-de-medicamentos-mayo-a-septiembre-2024.csv | inventario | cp1252 | `;` | no | 2,645 |
| inventario-de-medicamentos-nov.-2022.csv | inventario | cp1252 | `;` | no | 594 |
| inventario-de-medicamentos-noviembre-2021.csv | inventario | cp1252 | `;` | sí | 535 |
| inventario-de-medicamentos-octubre-2021.csv | inventario | cp1252 | `;` | sí | 535 |
| inventario-de-medicamentos-octubre-2022.csv | inventario | cp1252 | `;` | no | 577 |
| inventario-de-medicamentos-octubre-2024.csv | inventario | cp1252 | `;` | no | 531 |
| inventario-de-medicamentos-septiembre-2022.csv | inventario | cp1252 | `;` | no | 531 |
| inventario-medicamentos-agosto-2021.csv | inventario | cp1252 | `;` | sí | 534 |
| inventario-medicamentos-junio-2022.csv | inventario | cp1252 | `;` | no | 530 |
| inventario-medicamentos-septiembre-2021.csv | inventario | cp1252 | `;` | sí | 534 |
| invetario-de-medicamentos-agosto-2022.csv | inventario | cp1252 | `;` | no | 596 |
