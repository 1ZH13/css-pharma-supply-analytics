# Recomendaciones, riesgos y limitaciones (Etapa 6)

Corte de datos: **septiembre 2026**. Las cifras vienen de `preguntas_resumen.json`, `kpi_resumen.json` y de las tablas de la rama `data`. El pipeline las recalcula cada mes.

## 1. Resumen para la gerencia

El inventario de la CSS vale **B/. 42.9 millones**. Eso es menos de la mitad del promedio mensual de 2021–2024, que fue de B/. 98–118 millones. Aun así, está mal distribuido:

- Hay **20 medicamentos críticos sin existencia** en los almacenes.
- Hay **81 medicamentos en riesgo alto**. De ellos, 50 son críticos.
- Hay **B/. 12.45 millones inmovilizados** en 43 medicamentos con más de 12 meses de cobertura.
- El interior del país tiene en cero entre el 23 % y el 27 % de los renglones que Panamá sí tiene.

Con los datos se pueden tomar decisiones concretas este mismo mes.

## 2. Recomendaciones por pregunta

| # | Hallazgo | Recomendación | Indicador para darle seguimiento |
|---|---|---|---|
| P1 | El valor del inventario cayó **64.3 %** entre oct-2024 y ene-2025, y las unidades cayeron 45.9 %. El precio mediano no cambió: se compró menos, no más barato. | Definir por escrito el **nivel objetivo de inventario** (meses de cobertura por categoría) y aprobarlo como política. Revisar los **B/. 12.45 M inmovilizados**: el 60 % está en un solo producto, apalutamida 60 mg (B/. 7.5 M, 52 meses de cobertura). Conviene confirmar su consumo real antes de volver a comprarlo. | Valor del inventario y dinero inmovilizado (P1) |
| P2 | La CSS anuncia **90–96 %** de abastecimiento. Los datos de los almacenes muestran **78.8–86.3 %**, con una brecha promedio de 11.4 puntos. | Publicar **un solo indicador** con su fórmula: qué se mide (almacén o farmacia), sobre cuántos renglones y en qué mes. Publicarlo cada mes junto al inventario abierto. | % de abastecimiento oficial frente al declarado (P2) |
| P3 | Asma/EPOC (27.1 %), terapia hormonal oncológica (25.0 %), oncológicos (23.9 %) y VIH pasan más meses en cero que los no críticos (18.0 %). | Priorizar compras y **stock de seguridad por grupo de pacientes**, no por renglón. Hay 16 oncológicos y 11 cardiovasculares en riesgo alto. Para los 17 críticos que también escasean en EE. UU. (openFDA), buscar **proveedor alterno o sustituto** desde ya. | % de meses en cero por grupo crítico (P3) |
| P4 | CDPA (Panamá) concentra el **80.1 %** del valor. CDDI y CDCH tienen en cero el 26.8 % y el 23.0 % de lo que otro centro sí tiene. | **Ejecutar los 143 traslados sugeridos** (B/. 1.69 M; 43 son de críticos) antes de comprar. Fijar un reparto mínimo de 2 meses de cobertura en cada almacén regional. | Traslados ejecutados y % en cero por centro (P4) |
| P5 | Desde que se instaló la Comisión de Desabastecimiento Crítico (oct-2025), el abastecimiento subió de 78.8 % a **86.3 %** y los críticos en cero bajaron de 31 a **20**. | Mantener la Comisión y la compra conjunta MINSA-CSS. Medir su efecto con estos mismos indicadores cada mes. La relación es temporal, no prueba causa. | Abastecimiento y críticos en cero, mes a mes (P5) |
| P6 | **23 medicamentos** siguen publicados en el catálogo con 12 meses consecutivos en cero. 5 son críticos (etopósido, melfalano, doxorubicina, lamivudina solución y propranolol 10 mg) y 4 nunca tuvieron existencia. | Para cada uno, decidir entre **reactivar la compra**, **definir un sustituto terapéutico** o **depurarlo del catálogo**. Atender primero los 5 críticos. | Número de medicamentos fantasma (P6) |

### Plan sugerido para los próximos 30 días
1. **Semana 1:** ejecutar los traslados hacia CDDI y CDCH de los medicamentos críticos. Reunir a la Comisión con la lista de los 50 críticos en riesgo alto.
2. **Semana 2:** compras urgentes o alternas para los críticos que no tienen existencia en ningún centro.
3. **Semana 3:** revisión clínica de los 23 medicamentos fantasma y de los 5 productos con más dinero inmovilizado.
4. **Semana 4:** publicar el indicador de abastecimiento con su fórmula y comparar contra este tablero.

## 3. Riesgos del sistema y cómo se mitigan

| Riesgo | Impacto | Mitigación implementada o propuesta |
|---|---|---|
| La CSS cambia el formato de los archivos (ya hubo 5 formatos y un cambio de código en 2025) | El pipeline deja de cargar el mes nuevo | Hay detección automática de codificación, separador y columnas. El reporte de calidad avisa si falta un mes o aparecen columnas nuevas. Hay 31 pruebas automáticas en CI. |
| Datos atípicos en la fuente (agosto 2024 fuera de escala) | KPI distorsionados | Columna `atipico`, excluida de los KPI y documentada en `docs/reporte_calidad.md`. |
| Faltan meses (nov–dic 2024 no se publicaron) | Series con huecos | Se muestran como hueco, no se rellenan. Se reportan en el reporte de calidad. |
| El consumo es estimado: la CSS publica existencias, no despachos | Cobertura sobre o subestimada (p. ej. ustekinumab sale con miles de meses) | Se usa la mediana de las caídas mensuales, un método conservador. Si la CSS entrega despachos reales, se reemplaza esa sola columna. |
| La IA generativa se equivoca o inventa | Titulares o respuestas falsas | Gemini solo redacta con cifras calculadas. Los titulares se validan contra los números y, si no coinciden, se usa una plantilla. El asistente responde únicamente con el contexto que le da el sistema. |
| Cuota gratuita de Gemini agotada | El asistente o el análisis de noticias no responden | Caché de respuestas, cambio automático de modelo y aviso claro en la app. El dashboard funciona sin IA. |
| Caída de MongoDB Atlas o de GitHub | El dashboard se queda sin datos | Streamlit lee primero MongoDB, luego archivos locales y luego la rama `data` de GitHub. |
| Credenciales expuestas | Acceso no autorizado a la base | Las claves viven en GitHub Secrets y Streamlit Secrets, nunca en el código. Se recomienda un usuario de Atlas con permisos solo sobre `css_pharma` y limitar el acceso de red de Atlas cuando el proyecto pase a producción. |
| Noticias con derechos de autor | Riesgo legal | No se publican los textos, solo el análisis estructurado de la IA (decisión del 22/11). |

## 4. Limitaciones del análisis

- Los datos cubren **solo los 3 almacenes centrales**, no las farmacias de policlínicas y hospitales. Un medicamento puede estar en cero en el almacén y existir en una farmacia, o al revés.
- Las categorías críticas se asignaron por código ATC. Son una propuesta que debe validar el rol de Farmacia.
- La relación entre la Comisión (P5) y la mejora es temporal. En el mismo periodo hubo compras y cambios de gestión.
- Las declaraciones públicas de abastecimiento (P2) se extrajeron de 6 noticias. Pueden existir otras.

## 5. Mejoras futuras

- **Alerta mensual automática** (GitHub Actions): cuando se publique un mes nuevo, enviar un resumen con los críticos que pasaron a cero y los traslados sugeridos.
- Integrar **despachos reales** para calcular el consumo y no estimarlo.
- Incluir las **farmacias** si la CSS publica sus existencias.
- Modelo de **pronóstico de quiebres** a 3 meses con la serie histórica.
