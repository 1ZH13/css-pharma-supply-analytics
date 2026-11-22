# Fuentes de datos

## 1. Inventario de medicamentos — Caja de Seguro Social (estructurado)
- **Publica:** CSS, Dirección Nacional de Logística, Depto. de Planificación y Control de Inventarios.
- **Portal:** https://www.datosabiertos.gob.pa (organización `caja-de-seguro-social`), API CKAN `package_search`.
- **Licencia:** Creative Commons Attribution (CC BY).
- **Cobertura:** 2021 a III trimestre de 2026; 79 archivos CSV (también XLSX y PDF).
- **Centros de distribución:** CDPA = Panamá · CDDI = Divisa · CDCH = Chiriquí.
- **Dos familias de archivos:**
  - *Inventario / Cuadro de inventario*: por mes, existencias por centro, precio unitario, total y monto en B/.
  - *Cuadro comparativo*: total disponible por mes del año e incluye código **SAFIRO** (tipo ATC, ej. `A10BB00001`).

### Problemas de calidad detectados (los resuelve el pipeline)
| Problema | Ejemplo | Tratamiento |
|---|---|---|
| Separador distinto | `;` en 2022–2024, `,` en 2023 (comparativos) y 2025–2026 | Detección automática |
| Codificación | `DESCRIPCIàN`, `Nø` (CP850 leído como Latin-1) | Detección y corrección de codificación |
| Archivos sin encabezado | Inventarios mensuales 2023–2024 | Esquema por familia de archivo |
| Varios meses por archivo, en columnas | Trimestrales 2025–2026, mayo–sept. 2024 | Paso de formato ancho a largo (una fila por medicamento-mes-centro) |
| **Cambio de codificación de productos en 2025** | `101000801` → `1-01-0975-01` | Tabla de equivalencias por descripción normalizada |
| Números como texto | `"12,440,000"`, `B/.0.54` | Limpieza a numérico |
| Renglones de totales y filas vacías | fila `TOTAL` | Se eliminan |

## 2. openFDA — Drug Shortages (semiestructurado)
- **Endpoint:** `https://api.fda.gov/drug/shortages.json` — público, sin clave.
- **Uso:** cruzar por principio activo para distinguir escasez global (proveedor/fabricante) de problemas locales de compra o distribución.

## 3. Noticias e informes (no estructurado)
- Lista en `data/raw/texto/fuentes_texto.csv` (La Prensa, La Estrella de Panamá, Telemetro, Panamá América, Instituto Gorgas, OPS).
- **Uso:** IA generativa extrae medicamento mencionado, causa del desabastecimiento y fecha; se cruza con el inventario.

## Complementarias (contexto)
- ACODECO — Canasta Básica de Medicamentos (CABAMED, 153 productos): precio genérico vs. referencia en farmacias privadas.
- MINSA — programa de medicamentos a bajo costo (~140 fármacos en 110 farmacias públicas).
- INEC — instalaciones de salud por provincia.
