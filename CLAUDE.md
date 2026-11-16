# Viajes DGT — notas del proyecto

- Idioma: español, tono informal (tú). Horas en 24 h, importes en euros.
- Stack acordado: GitHub Actions + Python (solo librería estándar) para recolectar; frontend en HTML único con Leaflet (PWA) publicado en GitHub Pages. No introducir otro stack sin preguntar.
- Antes de modificar archivos existentes: resumen previo y confirmación. Una sola pregunta a la vez.
- Datos: feeds DATEX II de `nap.dgt.es` (ver `collector/common.py`, `SOURCES`). Estado actual en la rama `latest` (sin historial); histórico solo como diferencias en `data/history/`.
- Parsers de incidencias y paneles ajustados al XML real; el de capas estáticas es genérico. Muestras en `data/samples/`, etiquetas en `meta.leaf_tags`. Nombres reales: `roadName`, `tpegDirectionRoad`, `kilometerPoint`, `causeType`, `vmsControllerReference@id` (= id de paneles_loc).
- Fases: 1 recolector (hecha) · 2 planificador web · 3 tiempo en ruta · 4 calidad de dato y tramos de riesgo · 5 alertas y modo conducción.
- Pendiente de decidir: repo privado impide GitHub Pages en plan gratuito; valorar hacerlo público (los datos son públicos de la DGT).
