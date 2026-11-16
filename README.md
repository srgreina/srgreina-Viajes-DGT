# Viajes DGT

Planificador de trayectos con datos oficiales de la DGT (NAP, `nap.dgt.es`): estado de la ruta, incidencias, paneles, radares fijos, cámaras, tiempo a lo largo del recorrido y avisos oficiales de AEMET.

**Estado: fases 1 a 4.** Recolector con histórico, planificador web (`docs/`), tiempo/avisos en ruta, calidad de dato, tramos de riesgo y carga VE.

## Planificador web (`docs/index.html`)

HTML único con Leaflet, instalable como PWA. Se publica con GitHub Pages (Settings → Pages → *Deploy from a branch* → `main` → `/docs`): `https://srgreina.github.io/srgreina-Viajes-DGT/`.

1. Origen y destino con Nominatim (solo al pulsar Buscar o Intro, sin autocompletar) o tu ubicación. Salida configurable.
2. Ruta en coche con el servidor público de OSRM; de ahí salen los kilómetros y la hora estimada de paso (sin tráfico).
3. Cruce de la ruta con incidencias, paneles, radares fijos y cámaras a menos de 150 m del trazado (rejilla espacial; tramos de incidencia muestreados cada 120 m).
4. Resumen ordenado por kilómetro de ruta, con hora de paso, gravedad (corte o accidente = grave) y mapa. Las capas se eligen con interruptores y se guardan en el móvil; cada feed solo se descarga cuando su capa está activa.
5. **Tiempo en ruta** (Open-Meteo, gratuito, sin clave, CC-BY 4.0): previsión horaria en puntos cada ≈25 km (máx. 40) a la hora de paso. Avisa de lluvia ≥5 mm/h, rachas ≥70 km/h, hielo o nieve, visibilidad <1 km y tormenta. Alcance: ≈15 días.
6. **Avisos AEMET** (capa opcional): cruza la ruta (muestreo ≈1,5 km) con los polígonos de los avisos CAP vigentes a la hora de paso; amarillo = media, naranja/rojo = grave. Si no hay `avisos.json` (sin clave), el planificador lo indica y sigue.
7. **Calidad de dato**: la cabecera muestra la fiabilidad (buena/media/baja) y el resumen avisa si no es buena (huecos del recolector, retraso del feed, paneles sin localización, incidencias con fin previsto vencido, marcadas en la lista).
8. **Carga VE** (capa opcional, desactivada): puntos de recarga del NAP con ≥ 50 kW a menos de 1,5 km de la ruta (potencia, conectores, operador, 24 h).
9. **Tramos de riesgo** (capa opcional, desactivada): tramos de 1 km con ≥ 3 incidencias no planificadas repetidas (accidentes, averías, objetos en calzada, retenciones; las obras no cuentan). Avisa si hay menos de 30 días de histórico.
10. Lee los datos de la rama `latest` (`raw.githubusercontent.com`) y avisa si tienen más de 30 min.

Tests de la lógica de cruce: `node --test tests/core.test.mjs` (extrae el bloque `<core>` de `index.html`).

## Cómo funciona el recolector

| Qué | Dónde | Frecuencia |
|---|---|---|
| Incidencias (DATEX II v3.7) y paneles de mensaje variable (v3.7) | `collector/realtime.py` → workflow `collect.yml` | cada ≈10 min: cada ejecución relanza la siguiente (job `siguiente`); el cron de Actions queda de respaldo |
| Avisos meteorológicos de AEMET (CAP) | `collector/aemet.py`, paso opcional de `collect.yml` | cada ejecución, pero solo descarga si el estado tiene >25 min |
| Calidad de dato (`latest/calidad.json`) | `collector/calidad.py`, paso de `collect.yml` | cada ejecución (lee `data/history/runs`, ventana de 24 h) |
| Tramos de riesgo (`data/static/riesgo.json`) | `collector/riesgo.py`, paso de `static.yml` | diario; incremental, acumulado en `data/history/riesgo_estado.json` (solo días completos) |
| Radares fijos, cámaras, localizaciones de paneles y puntos de recarga VE | `collector/static_layers.py` → workflow `static.yml` | diario, 03:15 UTC |

Solo usa la librería estándar de Python (3.11+). Sin dependencias.

### Dónde quedan los datos

- **Rama `latest`** (se sobrescribe en cada ejecución, sin historial): `incidencias.json`, `paneles.json` y `static/*.json`. Es lo que leerá el frontend.
- **`data/static/`** (rama `main`): capas estáticas; solo cambian cuando cambian los datos de origen.
- **`data/history/`** (rama `main`): solo diferencias, nunca instantáneas completas.
  - `incidencias/AAAA-MM-DD.jsonl` y `paneles/AAAA-MM-DD.jsonl`: eventos `open`, `change` y `close`. Los eventos de la primera ejecución llevan `"boot": true`.
  - `runs/AAAA-MM.jsonl`: una línea por ejecución y feed (`ok`, `ms`, `bytes`, `published`, `lag_s`, `count`, `opens`, `changes`, `closes`, `err`). Base de la calidad de dato.
- **`data/samples/*.head.xml`**: primeros 40 KB del XML crudo de cada feed, guardados una sola vez para ajustar los parsers.

### Avisos AEMET: clave

Necesita el secreto del repo `AEMET_API_KEY` (Settings → Secrets and variables → Actions → New repository secret; clave gratuita de AEMET OpenData). Sin él, el paso se omite sin error. Salida `latest/avisos.json`: `items[{id, zone, ev, ph, lvl, area, desc, from, to, poly}]` (polígonos `[lat, lon]` a 3 decimales; se descartan cancelados, caducados y los sustituidos por una actualización). La primera ejecución guarda una muestra en `data/samples/aemet_cap.sample.xml`. El parser sigue el CAP 1.2 publicado por AEMET (bloque `es-ES`, nivel en `AEMET-Meteoalerta nivel`).

### Formato de `incidencias.json`

```json
{"generated":"…Z","published":"…","count":123,"meta":{"leaf_tags":{}},
 "items":[{"id":"18811074","sit":"2816645","ver":"2","kind":"MaintenanceWorks",
           "types":["roadMaintenance","roadworks","narrowLanes"],"status":"active","created":"…","start":"…",
           "road":"N-400","dir":"both","lanes":"…","pk":[37.1,37.3],"a":[lat,lon],"b":[lat,lon],
           "geo":{"province":"…","municipality":"…","autonomousCommunity":"…"},"text":"…"}]}
```

Los campos vacíos se omiten. Coordenadas a 6 decimales.

## Uso local

```bash
python -m unittest discover -s tests -v            # tests del recolector (XML sintético)
node --test tests/core.test.mjs                    # tests del planificador
python collector/realtime.py --prev prev --out latest
python collector/static_layers.py --out data/static
```

## Limitaciones conocidas

- **Parking:** el NAP solo publica la ocupación de aparcamientos urbanos de ayuntamientos; no hay datos de aparcamientos o áreas de descanso en carretera, así que esa capa no se ha hecho.
- **Carga VE:** feed estático (se actualiza cada 24 h), sin disponibilidad en tiempo real. Unos 12.000 sitios, fusionados por punto y operador; `static/recarga.json` pesa unos MB y solo se descarga al activar la capa.
- **Tramos de riesgo:** el histórico empieza el 2026-11-16 y crece ≈1,5 MB/día en `data/history/` (vigila el tamaño del repo a medio plazo). Hasta acumular semanas, los tramos son poco fiables.
- Los parsers de **incidencias** y **paneles** están ajustados al XML real (muestras en `data/samples/`). El de las **capas estáticas** (radares, cámaras, localizaciones de paneles) es genérico y su salida está revisada, pero conviene reajustarlo si la DGT cambia el perfil. Los radares fijos solo se publican en DATEX II v2 y su fecha de publicación es antigua (2025-12).
- OSRM y Nominatim públicos no tienen garantía de servicio ni admiten uso intensivo; el enrutador es fácil de cambiar (`fetchRoute`).
- El planificador no filtra por sentido de circulación: una incidencia de la otra calzada puede aparecer (se indica el sentido en el texto).
- El cron de GitHub Actions puede retrasarse o no dispararse; por eso `collect` se autoencadena. Aun así el intervalo no es exacto y el histórico no es continuo.
- Los feeds de la DGT están sujetos a su [aviso legal](https://www.dgt.es/contenido/aviso-legal/) (CC-BY). Cubren la red estatal salvo País Vasco y Cataluña.

## Fases

1. Recolector, histórico y capas estáticas (hecha).
2. Planificador web: ruta, cruce con capas y selector de capas (hecha).
3. Tiempo a lo largo de la ruta según la hora de paso y avisos AEMET (hecha).
4. Calidad de dato, tramos de riesgo y carga VE (hecha).
5. Alertas de corredor, resumen semanal y modo conducción por voz.
