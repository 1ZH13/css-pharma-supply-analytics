# Indicadores gerenciales (Etapa 4)

Los calcula `python -m pipeline.kpi` a partir de las tablas limpias. Se excluyen las filas marcadas `atipico`.

## Indicadores mensuales (`kpi_mensual`, `kpi_centro`)

| KPI | Fórmula | Lectura gerencial |
|---|---|---|
| Valor del inventario (B/.) | Σ cantidad × precio efectivo | Capital inmovilizado en los almacenes |
| % de abastecimiento | 100 − % de renglones con existencia nacional = 0 | Comparable con el "% de abastecimiento" que anuncia la CSS |
| Renglones en cero | Renglones publicados con existencia total = 0 | Quiebres de stock a nivel nacional |
| Críticos en cero | Renglones en cero de categorías críticas (insulinas, oncológicos, VIH, cardiovascular…) | Impacto directo en pacientes crónicos |
| Participación por centro | Valor del centro ÷ valor total | Concentración del inventario en CDPA, CDDI y CDCH |
| % en cero por centro | Renglones en cero en el centro ÷ renglones | Desbalance regional |

## Riesgo por medicamento (`riesgo_medicamentos`)

- **Consumo aparente mensual**: la CSS publica existencias, no despachos. Se estima como la **mediana de las disminuciones de existencia mes a mes** en los últimos 12 meses; los meses con reposición (existencia sube) se ignoran. Es una aproximación conservadora.
- **Cobertura (meses)** = existencia actual ÷ consumo aparente.
- **Puntaje de riesgo (0–100)**:

| Señal | Puntos |
|---|---|
| Sin existencia | 40 |
| Cobertura < 1 / < 2 / < 3 meses | 35 / 25 / 15 |
| Meses en cero en los últimos 12 | 2 por mes (máx. 20) |
| Existencias cayendo > 30 % en 6 meses | 10 |
| Medicamento crítico | 15 |
| Reportado como faltante en noticias (IA) | 10 |
| Escasez vigente en EE. UU. (openFDA) | 5 |

Nivel: **alto** ≥ 60 · **medio** 35–59 · **bajo** < 35.

## Redistribución entre centros (`redistribucion`)

Para cada medicamento y centro se calcula la cobertura con el consumo aparente del propio centro:

- Un centro **necesita** si su cobertura es < 1 mes; **puede ceder** si es > 4 meses.
- Se sugiere transferir lo necesario para llevar al centro con déficit a **2 meses**, sin dejar al origen por debajo de 2 meses.
- La lista se ordena por medicamentos críticos y por valor transferido.

## Limitaciones

- No hay datos de consumo real ni de pedidos en tránsito: una existencia en cero puede estar por reponerse.
- Noviembre y diciembre de 2024 no fueron publicados.
- La categoría crítica es una propuesta por código ATC que debe validar la Dirección Nacional de Farmacia.
