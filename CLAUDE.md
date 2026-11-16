# Viajes DGT — notas del proyecto

- Idioma: español, tono informal (tú). Horas en 24 h, importes en euros.
- Stack acordado: GitHub Actions + Python (solo librería estándar) para recolectar; frontend en HTML único con Leaflet (PWA) publicado en GitHub Pages. No introducir otro stack sin preguntar.
- Antes de modificar archivos existentes: resumen previo y confirmación. Una sola pregunta a la vez.
- Datos: feeds DATEX II de `nap.dgt.es` (ver `collector/common.py`, `SOURCES`). Estado actual en la rama `latest` (sin historial); histórico solo como diferencias en `data/history/`.
- Parsers de incidencias y paneles ajustados al XML real; el de capas estáticas es genérico. Muestras en `data/samples/`, etiquetas en `meta.leaf_tags`. Nombres reales: `roadName`, `tpegDirectionRoad`, `kilometerPoint`, `causeType`, `vmsControllerReference@id` (= id de paneles_loc).
- Fases: 1 recolector (hecha) · 2 planificador web (hecha, `docs/index.html`) · 3 tiempo en ruta y avisos AEMET (hecha) · 4 calidad de dato, tramos de riesgo y carga VE (hecha) · 5 alertas y modo conducción.
- Repo público (decidido). Publicación con GitHub Pages desde `main` + `/docs`.
- `docs/index.html`: lógica pura entre `// <core>` y `// </core>` (testeada en `tests/core.test.mjs`); no tocar esos marcadores. Rutas con OSRM público, geocodificación con Nominatim sin autocompletar (política de uso).
- Tiempo: Open-Meteo (sin clave) desde el navegador. Avisos AEMET: `collector/aemet.py` con secreto `AEMET_API_KEY` (opcional, nunca pedirle la clave al usuario ni ponerla en el repo); salida `latest/avisos.json`. Los puntos de muestreo (`samplePoints`) están en `<core>` y tienen tests.
- Fase 4: `collector/calidad.py` (en collect), `collector/riesgo.py` (en static, incremental, estado en `data/history/riesgo_estado.json`), `parse_recarga` en `parsers.py`. Concurrencia: `collect` y `static` tienen grupos distintos (la cadena de collect dejaría sin ejecutar a static); los push a main reintentan con `pull --rebase`.
