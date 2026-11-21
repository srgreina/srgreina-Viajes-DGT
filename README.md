# Viajes DGT

Planificador de trayectos con datos oficiales de la DGT (NAP, `nap.dgt.es`): estado de la ruta, incidencias, paneles, radares fijos, cámaras, tiempo a lo largo del recorrido y avisos oficiales de AEMET.

**Estado: fases 1 a 4 y alertas de corredor (fase 5, parte 1).** Recolector con histórico, planificador web (`docs/`), tiempo/avisos en ruta, calidad de dato, tramos de riesgo y carga VE.

## Planificador web (`docs/index.html`)

HTML único con Leaflet, instalable como PWA. Se publica con GitHub Pages (Settings → Pages → *Deploy from a branch* → `main` → `/docs`): `https://srgreina.github.io/srgreina-Viajes-DGT/`.

1. Origen y destino en dos campos de solo texto. Al tocarlos se despliega: *Mi ubicación* (solo origen), tus favoritos y los lugares recientes (se filtran al escribir). La búsqueda con Nominatim va con Intro o al salir del campo (sin autocompletar); cada resultado lleva una estrella para guardarlo como favorito. Los municipios se centran en su núcleo urbano (Open-Meteo/GeoNames). Favoritos, rutas recientes y corredores se guardan solo en el navegador. Salida configurable.
2. Ruta en coche con el servidor público de OSRM; de ahí salen los kilómetros y la hora estimada de paso (sin tráfico).
3. Cruce de la ruta con incidencias, paneles, radares fijos y cámaras a menos de 150 m del trazado (rejilla espacial; tramos de incidencia muestreados cada 120 m).
4. Resumen ordenado por kilómetro de ruta, con hora de paso, gravedad (corte o accidente = grave) y mapa. Las capas se eligen con interruptores y se guardan en el móvil; cada feed solo se descarga cuando su capa está activa. La interfaz es un mapa a pantalla completa con panel inferior de tres alturas (lateral en escritorio) y línea de PK con los avisos colgados de la ruta.
5. **Tiempo en ruta** (Open-Meteo, gratuito, sin clave, CC-BY 4.0): previsión horaria en puntos cada ≈25 km (máx. 40) a la hora de paso. Avisa de lluvia ≥5 mm/h, rachas ≥70 km/h, hielo o nieve, visibilidad <1 km y tormenta. Alcance: ≈15 días.
6. **Avisos AEMET** (capa opcional): cruza la ruta (muestreo ≈1,5 km) con los polígonos de los avisos CAP vigentes a la hora de paso; amarillo = media, naranja/rojo = grave. Si no hay `avisos.json` (sin clave), el planificador lo indica y sigue.
7. **Calidad de dato**: la cabecera muestra la fiabilidad (buena/media/baja) y el resumen avisa si no es buena (huecos del recolector, retraso del feed, paneles sin localización, incidencias con fin previsto vencido, marcadas en la lista).
8. **Carga VE** (capa opcional, desactivada): puntos de recarga del NAP con ≥ 50 kW a menos de 1,5 km de la ruta (potencia, conectores, operador, 24 h).
9. **Tramos de riesgo** (capa opcional, desactivada): tramos de 1 km con ≥ 3 incidencias no planificadas repetidas (accidentes, averías, objetos en calzada, retenciones; las obras no cuentan). Avisa si hay menos de 30 días de histórico.
10. **Corredores** (panel "Mis corredores"): guarda un trayecto con días y hora habitual (se almacena solo en el móvil). "Ver" lo recalcula para su próxima salida. "Copiar para avisos al móvil" exporta los corredores para el servidor (ver abajo).
11. Botón para limpiar la ruta, panel lateral ajustable en escritorio (el tamaño de letra escala con el ancho) y etiqueta con los datos del trayecto al pasar el ratón por la ruta.
12. **Modo conducción** (botón del altavoz, con ruta calculada): sigue tu GPS sobre la ruta y dice en voz alta (voz del navegador, en español) lo que hay a menos de 5 km por delante: incidencias, avisos AEMET, tiempo adverso, radares, paneles y tramos de riesgo; primero lo grave, máx. 2 por lectura y sin repetir. Avisa si te sales de la ruta (>300 m) y cuando vuelves. Mantiene la pantalla encendida (con la pantalla apagada el móvil pausa GPS y voz).
13. **Refresco automático:** con ruta calculada y la pantalla visible, cada 5 min (y al volver a la pestaña) vuelve a pedir incidencias, paneles, avisos AEMET y fiabilidad, y recalcula lo que cae en la ruta; el tiempo se renueva cada 15 min. En modo conducción no repite lo ya dicho. Si un refresco falla, se conservan los datos anteriores.
14. **Solo mi sentido** (activado por defecto, conmutador junto a las capas): oculta lo del otro sentido. Tu sentido se calcula por tramo con la carretera que da OSRM (`steps`) y los PK de cámaras, paneles e incidencias cercanos (≥90 % de pares de acuerdo, se descartan como mucho un 20 % de referencias atípicas; si no, «sin determinar» y se muestra todo). Radares y paneles: solo los de tu sentido en cualquier vía. Incidencias: solo se ocultan obras, carriles cortados, averías, retenciones y similares del otro sentido en autovía o autopista estatal (A-, AP-, R- de 1–2 cifras); accidentes, cortes, desvíos, meteo, convencionales y «ambos sentidos» se ven siempre. Cámaras sin filtro. En la DGT «positive» = PK creciente (comprobado con radares C/D, tramos de radar y orden de PK de las incidencias). El resumen muestra el sentido calculado y cuántos elementos oculta. El modo conducción usa la misma lista. Versión visible al pie del panel, con el botón «Probar voz y GPS». En la APK, selector «Voz por»: manos libres del coche (por defecto; abre el canal de llamada Bluetooth y el coche silencia la radio), Bluetooth o altavoz bajando la música del móvil, o altavoz del móvil. Si el manos libres no abre en 4 s, habla por el audio normal y la prueba lo indica (plugin nativo `VozCochePlugin.java`).
15. **Conducción libre** (v27, botón del altavoz sin ruta calculada): con el GPS deduce carretera, PK y sentido (`locateOnRoad`: tramos entre referencias de PK de la DGT, coherencia PK/distancia, histéresis; la carretera nueva se busca con los últimos 25 s) y, cada 30 s, la confirma con OSRM `/match` (radio 20 m; si en 2 min no responde, «sin confirmar»). Avisa de lo que tienes delante en tu carretera y sentido (`aheadOnRoad`); sin carretera conocida, solo accidentes, cortes y retenciones en un cono de ±35° (`aheadCone`). Distancia de aviso según velocidad (≈2,5 min, 1,5–6 km); lo grave se repite a 1 km; por voz solo accidentes, cortes, retenciones, carriles cortados, radares y paneles que mencionan algo grave (también en modo ruta). Avisa si los datos de la DGT tienen más de 15 min y de avisos AEMET naranja/rojo al entrar en su zona. En la APK, notificación fija con el próximo aviso. Graba el trayecto solo en el móvil («Copiar trayecto», texto compacto `encodeTrack`) para reproducirlo en pruebas. Con la ruta borrada durante la conducción, sigue en conducción libre. Conduciendo, los datos se refrescan cada 5 min también con la pantalla apagada.
16. Lee los datos de la rama `latest` (`raw.githubusercontent.com`) y avisa si tienen más de 30 min.

El service worker (`docs/sw.js`) va a la red primero con `cache: 'no-store'` (evita la caché de 10 min de GitHub Pages); Leaflet y la tipografía van de caché. Tras un despliegue puede hacer falta recargar dos veces (Ctrl+F5). Cada cambio del front sube la versión `CACHE` y `VERSION` de `index.html` a la vez (un test lo comprueba).

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
- **`data/static/`** (rama `data`): capas estáticas; solo cambian cuando cambian los datos de origen.
- **`data/history/`** (rama `data`): solo diferencias, nunca instantáneas completas.
  - `incidencias/AAAA-MM-DD.jsonl` y `paneles/AAAA-MM-DD.jsonl`: eventos `open`, `change` y `close`. Los eventos de la primera ejecución llevan `"boot": true`.
  - `runs/AAAA-MM.jsonl`: una línea por ejecución y feed (`ok`, `ms`, `bytes`, `published`, `lag_s`, `count`, `opens`, `changes`, `closes`, `err`). Base de la calidad de dato.
- **`data/samples/*.head.xml`**: primeros 40 KB del XML crudo de cada feed, guardados una sola vez para ajustar los parsers.

### Resumen semanal de cortes (ntfy)

`collector/resumen.py` (workflow `resumen.yml`, lunes ≈08:00 hora de Madrid, también manual) lee los últimos 7 días del histórico y manda por ntfy los cortes (`roadClosed`/`carriagewayClosures`) de Andalucía —por carretera, con horas cortadas y si siguen abiertos— y los que han caído sobre tus corredores si existe el secreto `CORREDORES`. Los cortes por obras se cuentan aparte. Sin `NTFY_TOPIC` solo imprime el resumen.

### Limpieza del histórico

`collector/limpieza.py` (workflow `limpieza.yml`, domingos por la noche, también manual) borra de `data/history/` las incidencias y paneles de más de 8 días —así siempre queda la semana del resumen— y solo si `riesgo.py` ya procesó ese día; de `runs/` conserva el mes actual y el anterior. No toca `riesgo_estado.json`.

### Rama `data` y compactación mensual

El histórico, las capas estáticas y las muestras viven en la rama **`data`** (raíz: `history/`, `static/`, `samples/`; los workflows la sacan en `./data`). `main` solo cambia con el código, así que Pages no se reconstruye cada 10 min. `compactar.yml` (día 1 de cada mes, también manual) sustituye todo el historial de `data` por un único commit con lo que hay ahora, para que el repo no crezca (≈1,5 MB/día sin compactar). `main` no se toca. GitHub libera el espacio con retraso.

### Avisos de corredor al móvil (ntfy)

`collector/corredores.py` (paso de `collect.yml`) avisa por [ntfy.sh](https://ntfy.sh) cuando, entre 15 min antes y 90 min después de la hora habitual de un corredor, hay en su ruta: incidencias graves (corte, accidente, vehículo en llamas, desprendimientos, avalancha, inundación) a menos de 150 m, avisos AEMET naranja/rojo vigentes a la hora de paso, o tiempo adverso (lluvia ≥ 5 mm/h, rachas ≥ 70 km/h, hielo o nieve, visibilidad < 1 km, tormenta). Solo repite el aviso si el conjunto de alertas cambia.

Dos secretos del repo (Settings → Secrets and variables → Actions); sin ellos el paso se omite:
- `NTFY_TOPIC`: tema de ntfy, largo y aleatorio (quien lo conozca puede leer tus avisos). Se suscribe la app ntfy del móvil al mismo tema.
- `CORREDORES`: el JSON que copia el planificador. **El repo es público: el recorrido solo vive en el secreto y en el navegador.** El estado de avisos enviados (`latest/corredores_estado.json`) solo guarda hashes. Si guardas o borras corredores en la app, hay que volver a copiar y pegar el secreto. La línea se simplifica a ≤ 250 puntos, así que la precisión del cruce es algo menor que en la app.

Los mensajes pasan por los servidores de ntfy.sh (con el tema como única "contraseña").

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

- **Corredores:** el servidor usa duración sin tráfico y la zona horaria Europe/Madrid; el aviso depende de que el cron/cadena de `collect` esté activo en esa ventana (cada ≈10 min).
- **Parking:** el NAP solo publica la ocupación de aparcamientos urbanos de ayuntamientos; no hay datos de aparcamientos o áreas de descanso en carretera, así que esa capa no se ha hecho.
- **Carga VE:** feed estático (se actualiza cada 24 h), sin disponibilidad en tiempo real. Unos 12.000 sitios, fusionados por punto y operador; `static/recarga.json` pesa unos MB y solo se descarga al activar la capa.
- **Tramos de riesgo:** el histórico empieza el 2026-11-16 y crece ≈1,5 MB/día en la rama `data` (se compacta cada mes). Hasta acumular semanas, los tramos son poco fiables.
- Los parsers de **incidencias** y **paneles** están ajustados al XML real (muestras en `data/samples/`). El de las **capas estáticas** (radares, cámaras, localizaciones de paneles) es genérico y su salida está revisada, pero conviene reajustarlo si la DGT cambia el perfil. Los radares fijos solo se publican en DATEX II v2 y su fecha de publicación es antigua (2025-12).
- OSRM y Nominatim públicos no tienen garantía de servicio ni admiten uso intensivo; el enrutador es fácil de cambiar (`fetchRoute`).
- Filtro por sentido: depende de que la DGT etiquete bien el sentido (en paneles y cámaras ~3 % incoherente) y de que OSRM dé la carretera de cada tramo; ante la duda se muestra.
- El cron de GitHub Actions puede retrasarse o no dispararse; por eso `collect` se autoencadena. Aun así el intervalo no es exacto y el histórico no es continuo.
- Los feeds de la DGT están sujetos a su [aviso legal](https://www.dgt.es/contenido/aviso-legal/) (CC-BY). Cubren la red estatal salvo País Vasco y Cataluña.

## Fases

1. Recolector, histórico y capas estáticas (hecha).
2. Planificador web: ruta, cruce con capas y selector de capas (hecha).
3. Tiempo a lo largo de la ruta según la hora de paso y avisos AEMET (hecha).
4. Calidad de dato, tramos de riesgo y carga VE (hecha).
5. Alertas de corredor y resumen semanal y modo conducción por voz (hechos).
