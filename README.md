# Viajes DGT

Planificador de trayectos con datos oficiales de la DGT (NAP, `nap.dgt.es`): estado de la ruta, incidencias, paneles, radares fijos, cámaras y, más adelante, tiempo a lo largo del recorrido.

**Estado: fase 1 — recolector e histórico.** El planificador web llega en la fase 2.

## Cómo funciona

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
python -m unittest discover -s tests -v            # tests (XML sintético)
python collector/realtime.py --prev prev --out latest
python collector/static_layers.py --out data/static
```

## Limitaciones conocidas

- Los parsers de **incidencias** y **paneles** están ajustados al XML real (muestras en `data/samples/`). El de las **capas estáticas** (radares, cámaras, localizaciones de paneles) es genérico y su salida está revisada, pero conviene reajustarlo si la DGT cambia el perfil. Los radares fijos solo se publican en DATEX II v2 y su fecha de publicación es antigua (2025-12).
- El cron de GitHub Actions puede retrasarse varios minutos y no garantiza intervalo fijo; el histórico no es continuo.
- Los feeds de la DGT están sujetos a su [aviso legal](https://www.dgt.es/contenido/aviso-legal/) (CC-BY). Cubren la red estatal salvo País Vasco y Cataluña.

## Fases

1. Recolector, histórico y capas estáticas (esta).
2. Planificador web: ruta, cruce con capas y selector de capas.
3. Tiempo a lo largo de la ruta según la hora de paso.
4. Calidad de dato y tramos de riesgo.
5. Alertas de corredor, resumen semanal y modo conducción por voz.
