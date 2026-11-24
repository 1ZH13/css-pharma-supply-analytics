# Guía de revisión del proyecto

Esta guía es para las compañeras que revisan el proyecto antes de la presentación del **miércoles 25 de noviembre de 2026**. Explica qué revisar, cómo reportar lo que encuentren y qué cambios pueden hacer ustedes mismas sin romper nada.

## 1. Qué hay que revisar

| Entregable | Dónde está | Qué mirar |
|---|---|---|
| Documento final (SIG-Semestral) | Word Online (enlace en el grupo) | Redacción, ortografía, que las cifras coincidan con el dashboard, referencias APA, su propia sección |
| Presentación | Enlace de la presentación (en el documento y en el grupo) | Su diapositiva, las notas del orador de su rol y los tiempos |
| Dashboard web | https://css-medicamentos-panama.streamlit.app | Que cada página cargue, que los filtros funcionen y que las cifras tengan sentido |
| Power BI | `dashboard/powerbi/` (abrir el `.pbip` o el `.pbix` de OneDrive) | Las 8 páginas, los segmentadores y la página **La respuesta** |
| Código y documentación | Este repositorio | README, `docs/recomendaciones.md`, `docs/kpi.md`, `docs/reporte_calidad.md` |

### Cifras de control (corte septiembre 2026)

Estas cifras deben ser iguales en el documento, la presentación y los dashboards:

| Indicador | Valor |
|---|---|
| Abastecimiento de los almacenes | 86.31 % (76 de 555 renglones en cero) |
| Críticos sin existencia | 20 |
| En riesgo alto / críticos en riesgo alto | 81 / 50 |
| Comprar ya / Reforzar compra | 19 / 31 |
| Traslados sugeridos | 143 por B/. 1.69 M (43 de críticos) |
| Valor del inventario | B/. 42.9 M |
| Dinero inmovilizado | B/. 12.45 M en 43 medicamentos |
| Medicamentos fantasma | 23 (5 críticos) |

Si ven una cifra distinta en algún lado, **repórtenla** (paso 2): no la cambien a mano en un solo lugar.

### Qué revisa cada rol

| Rol | Integrante | Foco de la revisión |
|---|---|---|
| Gerente de Logística y Cadena de Suministro | Liliana Coronado | Página **La respuesta** y **P4 · El interior** (traslados y reparto mínimo); sección 7 del documento (recomendaciones y riesgos); diapositivas de respuesta, P4, recomendaciones y riesgos |
| Gerente de Calidad y Atención al Asegurado | Mónica Serrano | Referencias APA y fundamentación teórica (sección 3); **P2** (90 % anunciado) y el uso de la IA; conclusiones (sección 8); diapositivas de IA y conclusiones |

## 2. Cómo reportar algo (lo recomendado)

La forma más simple y segura es abrir un **issue**:

1. Entren a la pestaña **Issues → New issue** y elijan la plantilla **Revisión**.
2. Escriban **dónde** está el problema (documento, presentación, Streamlit, Power BI o archivo del repo), **qué** está mal y **cómo debería quedar**.
3. Un issue por tema. Si es algo pequeño (una coma, una palabra), pueden juntar varios en un mismo issue.

César revisa los issues y aplica los cambios en todos los lugares donde aparece la misma cifra o el mismo texto.

## 3. Si quieren cambiar un archivo ustedes mismas

Pueden hacerlo, siempre con una rama y un pull request. **Nunca** se escribe directo en `main`, `qa` ni `develop`.

**Desde la web de GitHub (sin instalar nada):**

1. Abran el archivo y pulsen el lápiz (**Edit this file**).
2. Hagan el cambio.
3. En **Commit changes**, elijan **Create a new branch** y pónganle un nombre como `feature/revision-liliana` o `feature/revision-monica`.
4. Pulsen **Propose changes** y luego **Create pull request**. Verifiquen que la base sea **`develop`**, no `main`.
5. Esperen a que la verificación automática salga en verde. César revisa y mezcla.

**Con git en la computadora:**

```bash
git clone https://github.com/1ZH13/css-pharma-supply-analytics.git
cd css-pharma-supply-analytics
git checkout develop
git checkout -b feature/revision-<nombre>
# ...cambios...
git commit -am "docs: corrige redacción de recomendaciones"
git push -u origin feature/revision-<nombre>
# luego abrir el pull request hacia develop en GitHub
```

Mensajes de commit en español, con prefijo: `docs:` (textos), `fix:` (corrección), `feat:` (algo nuevo).

## 4. Qué sí y qué no

| Sí pueden | Mejor no (avisen primero) |
|---|---|
| Corregir textos, ortografía y redacción en `README.md` y `docs/` | Cambiar cifras a mano: salen del pipeline |
| Abrir issues con observaciones, dudas o ideas | Tocar `pipeline/` o `.github/workflows/` (automatización mensual) |
| Proponer cambios de textos en el dashboard (`dashboard/streamlit/vistas.py`) por pull request | Escribir en la rama `data` (solo la usa GitHub Actions) |
| Comentar en los pull requests | Mezclar pull requests, borrar ramas o cambiar la configuración del repositorio |
| Probar el dashboard y el asistente de IA | Subir claves, contraseñas o archivos `.env` |

**Asistente de IA:** úsenlo poco hasta el miércoles. Tiene una cuota gratuita diaria y lo necesitamos para la demo.

## 5. Respaldo

Antes de la revisión se guardó un respaldo del estado del proyecto:

- Rama `respaldo/2026-11-23-antes-pr29`: estado de `main` antes de las correcciones del 23/11.
- Rama `respaldo/2026-11-23-lista-para-revision`: estado de `main` entregado para esta revisión.
- Copia comprimida en OneDrive del equipo (`SIG/_respaldos/`).
- El documento y la presentación guardan su propio historial de versiones.

Si algo se rompe, se puede volver a cualquiera de esos puntos.

## 6. Fecha límite

Envíen sus observaciones **antes del martes 24 de noviembre a las 6:00 p. m.**, para tener tiempo de aplicarlas y ensayar.
