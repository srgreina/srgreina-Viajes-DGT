# Viajes DGT

Planificador de trayectos con datos oficiales de la DGT (NAP, `nap.dgt.es`): estado de la ruta, incidencias, paneles, radares fijos, cámaras y, más adelante, tiempo a lo largo del recorrido.

**Estado: fases 1 y 2.** Recolector con histórico y planificador web (`docs/`).

## Planificador web (`docs/index.html`)

HTML único con Leaflet, instalable como PWA. Se publica con GitHub Pages (Settings → Pages → *Deploy from a branch* → `main` → `/docs`): `https://srgreina.github.io/srgreina-Viajes-DGT/`.

1. Origen y destino con Nominatim (solo al pulsar Buscar o Intro, sin autocompletar) o tu ubicación. Salida configurable.
2. Ruta en coche con el servidor público de OSRM; de ahí salen los kilómetros y la hora estimada de paso (sin tráfico).
3. Cruce de la ruta con incidencias, paneles, radares fijos y cámaras a menos de 150 m del trazado (rejilla espacial; tramos de incidencia muestreados cada 120 m).
4. Resumen ordenado por kilómetro de ruta, con hora de paso, gravedad (corte o accidente = grave) y mapa. Las capas se eligen con interruptores y se guardan en el móvil; cada feed solo se descarga cuando su capa está activa.
5. Lee los datos de la rama `latest` (`raw.githubusercontent.com`) y avisa si tienen más de 30 min.

Tests de la lógica de cruce: `node --test tests/core.test.mjs` (extrae el bloque `<core>` de `index.html`).

## Cómo funciona el recolector

| Qué | Dónde | Frecuencia |
|---|---|---|
| Incidencias (DATEX II v3.7) y paneles de mensaje variable (v3.7) | `collector/realtime.py` → workflow `collect.yml` | cada 10 min (cron de Actions, no es puntual) |
| Radares fijos, cámaras y localizaciones de paneles | `collector/static_layers.py` → workflow `static.yml` | diario, 03:15 UTC |

Solo usa la librería estándar de Python (3.11+). Sin dependencias.

### Dónde quedan los datos

- **Rama `latest`** (se sobrescribe en cada ejecución, sin historial): `incidencias.json`, `paneles.json` y `static/*.json`. Es lo que leerá el frontend.
- **`data/static/`** (rama `main`): capas estáticas; solo cambian cuando cambian los datos de origen.
- **`data/history/`** (rama `main`): solo diferencias, nunca instantáneas completas.
  - `incidencias/AAAA-MM-DD.jsonl` y `paneles/AAAA-MM-DD.jsonl`: eventos `open`, `change` y `close`. Los eventos de la primera ejecución llevan `"boot": true`.
  - `runs/AAAA-MM.jsonl`: una línea por ejecución y feed (`ok`, `ms`, `bytes`, `published`, `lag_s`, `count`, `opens`, `changes`, `closes`, `err`). Base de la calidad de dato.
- **`data/samples/*.head.xml`**: primeros 40 KB del XML crudo de cada feed, guardados una sola vez para ajustar los parsers.

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

- Los parsers de **incidencias** y **paneles** están ajustados al XML real (muestras en `data/samples/`). El de las **capas estáticas** (radares, cámaras, localizaciones de paneles) es genérico y su salida está revisada, pero conviene reajustarlo si la DGT cambia el perfil. Los radares fijos solo se publican en DATEX II v2 y su fecha de publicación es antigua (2025-12).
- OSRM y Nominatim públicos no tienen garantía de servicio ni admiten uso intensivo; el enrutador es fácil de cambiar (`fetchRoute`).
- El planificador no filtra por sentido de circulación: una incidencia de la otra calzada puede aparecer (se indica el sentido en el texto).
- El cron de GitHub Actions puede retrasarse varios minutos y no garantiza intervalo fijo; el histórico no es continuo.
- Los feeds de la DGT están sujetos a su [aviso legal](https://www.dgt.es/contenido/aviso-legal/) (CC-BY). Cubren la red estatal salvo País Vasco y Cataluña.

## Fases

1. Recolector, histórico y capas estáticas (hecha).
2. Planificador web: ruta, cruce con capas y selector de capas (hecha).
3. Tiempo a lo largo de la ruta según la hora de paso.
4. Calidad de dato y tramos de riesgo.
5. Alertas de corredor, resumen semanal y modo conducción por voz.
