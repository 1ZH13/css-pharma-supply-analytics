# Reporte Power BI

Proyecto en formato **PBIP** (texto, versionable en git):

- `CSS_inventario_medicamentos.pbip`: archivo que se abre con Power BI Desktop.
- `CSS_inventario_medicamentos.SemanticModel/`: modelo (TMDL). 14 tablas, relaciones, 23 medidas DAX y 2 columnas calculadas (acción y grupo de pacientes).
- `CSS_inventario_medicamentos.Report/`: reporte (PBIR). Tiene 8 páginas: Resumen, La respuesta y P1–P6, con segmentadores por año, centro, grupo de pacientes y acción.
- `generar_pbir.py`: regenera las páginas del reporte y los formatos de las medidas.

## Abrir y actualizar

1. Abrir `CSS_inventario_medicamentos.pbip` en Power BI Desktop.
2. Pulsar **Inicio → Actualizar**. Las tablas se leen de la rama `data` del repositorio con la función de Power Query `fnCSS`, que trae los CSV de `processed/`. No hace falta ninguna credencial.
3. Para entregar un solo archivo, usar **Archivo → Guardar como → .pbix**.

## Regenerar las páginas

Cerrar Power BI Desktop y ejecutar:

```
python dashboard/powerbi/generar_pbir.py dashboard/powerbi
```

El script hace lo siguiente:

- Mueve las páginas actuales a `_respaldo_paginas_<fecha>/`. Esa carpeta la ignora git.
- Escribe las 8 páginas de nuevo.
- Ajusta los formatos de las medidas y agrega (si faltan) las columnas y medidas de la respuesta.
