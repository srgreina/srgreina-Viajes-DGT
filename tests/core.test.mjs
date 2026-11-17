// Prueba la lógica pura del planificador: extrae el bloque <core> de docs/index.html.
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../docs/index.html', import.meta.url), 'utf8');
const core = html.slice(html.indexOf('// <core>'), html.indexOf('// </core>'));
const api = new Function(
  `${core}; return { buildRoute, nearest, nearestLine, collectHits, describe, fmtDur, fmtKm, fmtPk, samplePoints, pickHour, weatherAt, weatherAlerts, buildWeatherHits, weatherSummary, pointInRing, buildAvisoHits, avisoSummary, calidadResumen, collectCharge, collectRisk, simplifyLine, nextDeparture, corridorsExport, fmtDays, driveStep, driveSpeech };`,
)();

// Ruta recta de oeste a este por Málaga: lon -4.50 -> -4.40 a lat 36.70 (~8,9 km), 10 tramos.
const LAT = 36.7;
const coords = Array.from({ length: 11 }, (_, i) => [-4.5 + i * 0.01, LAT]);
const KM_PER_DEG_LON = 111.195 * Math.cos((LAT * Math.PI) / 180);
const totalM = 0.1 * KM_PER_DEG_LON * 1000;
const route = api.buildRoute(coords, null, { distance: totalM, duration: 3600 });
const offsetLat = (m) => LAT + m / 111195;

test('longitud y duración totales de la ruta', () => {
  assert.ok(Math.abs(route.totalD - totalM) < 1);
  assert.ok(Math.abs(route.totalT - 3600) < 1e-6);
});

test('un punto a 55 m entra y uno a 600 m no', () => {
  const near = api.nearest(route, offsetLat(55), -4.45);
  assert.ok(near && near.dist > 50 && near.dist < 60);
  assert.ok(Math.abs(near.s - totalM / 2) < 30); // a mitad de ruta
  assert.ok(Math.abs(near.t - 1800) < 10);
  assert.equal(api.nearest(route, offsetLat(600), -4.45), null);
});

test('un tramo perpendicular que cruza la ruta se detecta', () => {
  const h = api.nearestLine(route, [offsetLat(1000), -4.42], [offsetLat(-1000), -4.42]);
  assert.ok(h);
  assert.ok(Math.abs(h.s - totalM * 0.8) < 50);
});

test('un tramo paralelo lejano no se detecta', () => {
  assert.equal(api.nearestLine(route, [offsetLat(900), -4.49], [offsetLat(900), -4.41]), null);
});

test('collectHits ordena por kilómetro y respeta las capas activas', () => {
  const ds = {
    inc: { items: [
      { id: 'b', a: [offsetLat(10), -4.43], b: [offsetLat(10), -4.42], types: ['roadClosed'], road: 'A-7', pk: [1, 2] },
      { id: 'a', a: [offsetLat(10), -4.48], types: ['roadworks'] },
      { id: 'lejos', a: [offsetLat(5000), -4.45] },
    ] },
    rad: { items: [{ id: 'r', lat: offsetLat(20), lon: -4.46, road: 'A-7', pk: [3] }] },
    pan: { items: [{ id: 'p.1', ctrl: '7', texts: ['PRECAUCION'] }] },
    panLoc: { items: [{ id: '7', lat: offsetLat(30), lon: -4.41, road: 'A-7' }] },
  };
  const all = api.collectHits(route, ds, { inc: true, pan: true, rad: true, cam: false });
  assert.deepEqual(all.map((h) => h.item.id), ['a', 'r', 'b', 'p.1']);
  const soloRad = api.collectHits(route, ds, { inc: false, pan: false, rad: true, cam: false });
  assert.deepEqual(soloRad.map((h) => h.item.id), ['r']);
});

test('anotaciones de tiempo por tramo se respetan', () => {
  const ann = { distance: Array(10).fill(1000), duration: [60, 60, 60, 60, 60, 600, 60, 60, 60, 60] };
  const r2 = api.buildRoute(coords, ann, { distance: 10000, duration: 1200 });
  const h = api.nearest(r2, offsetLat(5), -4.40); // final de la ruta
  assert.ok(Math.abs(h.t - 1140) < 5); // suma de las anotaciones: 9 x 60 + 600
  const mid = api.nearest(r2, offsetLat(5), -4.45); // tras 5 tramos de 60 s
  assert.ok(Math.abs(mid.t - 300) < 5);
});

test('describe traduce y gradúa', () => {
  const d = api.describe({ layer: 'inc', item: { types: ['roadMaintenance', 'roadworks', 'roadClosed'], road: 'A-8005', pk: [0, 2.16], dir: 'both', geo: { municipality: 'Sevilla', province: 'Sevilla' } } });
  assert.equal(d.sev, 'high');
  assert.equal(d.title, 'Obras · Carretera cortada');
  assert.equal(d.sub, 'A-8005 · PK 0,0–2,2 · Sevilla, Sevilla · ambos sentidos');
  const low = api.describe({ layer: 'inc', item: { types: ['roadMaintenance', 'roadworks', 'narrowLanes'] } });
  assert.equal(low.sev, 'low');
  assert.equal(api.describe({ layer: 'inc', item: { types: ['fooBarType'] } }).title, 'Foo bar type');
  const veh = api.describe({ layer: 'inc', item: { types: ['vehicleObstruction', 'vehicleStuck'] } });
  assert.equal(veh.title, 'Vehículo detenido'); // el genérico se omite
  assert.equal(veh.sev, 'mid');
  const cl = api.describe({ layer: 'inc', item: { types: ['roadMaintenance', 'roadworks', 'carriagewayClosures'] } });
  assert.equal(cl.title, 'Obras · Cierre de calzada');
  assert.equal(cl.sev, 'high');
  assert.equal(api.describe({ layer: 'inc', item: { types: ['obstruction'] } }).title, 'Obstáculo'); // solo genérico: se muestra
});

test('formato de duración y distancia', () => {
  assert.equal(api.fmtDur(3600 * 5 + 12 * 60), '5 h 12 min');
  assert.equal(api.fmtDur(45 * 60), '45 min');
  assert.equal(api.fmtKm(531234), '531,2');
});

test('rendimiento: 5.000 puntos sobre una ruta de 20.000 vértices', () => {
  const big = Array.from({ length: 20001 }, (_, i) => [-6 + i * 0.0001, 37 + Math.sin(i / 500) * 0.2]);
  const r = api.buildRoute(big, null, { distance: 200000, duration: 7200 });
  const t0 = Date.now();
  let hits = 0;
  for (let i = 0; i < 5000; i++) {
    if (api.nearest(r, 37 + Math.random() * 0.4 - 0.2, -6 + Math.random() * 2)) hits++;
  }
  assert.ok(Date.now() - t0 < 1500, `tardó ${Date.now() - t0} ms`);
  assert.ok(hits >= 0);
});

// ---------------------------------------------------------------- tiempo en ruta
test('samplePoints: origen, intermedios y destino con su hora de paso', () => {
  const pts = api.samplePoints(route, 3000); // ruta de ~8,9 km, 3 h = 3600 s
  assert.equal(pts[0].s, 0);
  assert.ok(Math.abs(pts[pts.length - 1].s - totalM) < 1);
  assert.ok(Math.abs(pts[pts.length - 1].t - 3600) < 1e-6);
  assert.ok(pts.length >= 3 && pts.length <= 5, `puntos: ${pts.length}`);
  for (let i = 1; i < pts.length; i++) assert.ok(pts[i].s > pts[i - 1].s && pts[i].t > pts[i - 1].t);
  assert.ok(Math.abs(pts[1].lat - LAT) < 1e-9);
});

test('samplePoints: nunca más de 40 puntos y no duplica el destino', () => {
  const big = Array.from({ length: 2001 }, (_, i) => [-6 + i * 0.001, 37]);
  const r = api.buildRoute(big, null, { distance: 1_000_000, duration: 36000 });
  const pts = api.samplePoints(r, 25000);
  assert.ok(pts.length <= 42, `puntos: ${pts.length}`);
  assert.ok(pts[pts.length - 1].s - pts[pts.length - 2].s > 1000);
});

test('pickHour elige la hora más cercana y descarta lo que queda fuera', () => {
  const base = Date.UTC(2026, 10, 16, 12) / 1000;
  const times = [base, base + 3600, base + 7200];
  assert.equal(api.pickHour(times, (base + 3000) * 1000), 1);
  assert.equal(api.pickHour(times, (base - 600) * 1000), 0);
  assert.equal(api.pickHour(times, (base + 3 * 3600 + 5000) * 1000), null);
  assert.equal(api.pickHour([], 0), null);
});

test('weatherAlerts: umbrales', () => {
  const ok = { temp: 18, rain: 0.2, prob: 20, snow: 0, wind: 20, gust: 35, vis: 20000, code: 2 };
  assert.deepEqual(api.weatherAlerts(ok), []);
  const keys = (w) => api.weatherAlerts({ ...ok, ...w }).map((a) => a.key);
  assert.deepEqual(keys({ rain: 5 }), ['rain']);
  assert.deepEqual(keys({ rain: 4.9 }), []);
  assert.deepEqual(keys({ gust: 70 }), ['wind']);
  assert.deepEqual(keys({ temp: 2, rain: 0.5 }), ['ice']);
  assert.deepEqual(keys({ temp: 2, rain: 0 }), []);
  assert.deepEqual(keys({ snow: 0.2 }), ['ice']);
  assert.deepEqual(keys({ vis: 800 }), ['vis']);
  assert.deepEqual(keys({ code: 95 }), ['storm']);
  assert.deepEqual(api.weatherAlerts(null), []);
});

const hourly = (base, n, over = {}) => ({
  hourly: {
    time: Array.from({ length: n }, (_, i) => base + i * 3600),
    temperature_2m: Array(n).fill(15), precipitation: Array(n).fill(0), precipitation_probability: Array(n).fill(10),
    snowfall: Array(n).fill(0), wind_speed_10m: Array(n).fill(12), wind_gusts_10m: Array(n).fill(20),
    visibility: Array(n).fill(24000), weather_code: Array(n).fill(1), ...over,
  },
});

test('buildWeatherHits usa la hora de paso de cada punto y acepta objeto único o lista', () => {
  const dep = Date.UTC(2026, 10, 16, 12);
  const base = dep / 1000;
  const pts = api.samplePoints(route, 3000);
  // lluvia fuerte solo a la hora +2 (el punto final llega a las 13:00 -> hora +1)
  const rainy = hourly(base, 6, { precipitation: [0, 0, 8, 0, 0, 0] });
  const list = pts.map(() => rainy);
  const hits = api.buildWeatherHits(pts, list, dep);
  assert.equal(hits.length, pts.length);
  assert.ok(hits.every((h) => h.layer === 'wx' && h.dist === 0));
  assert.deepEqual(api.weatherSummary(hits, dep), []); // a la hora de paso nunca coincide con la +2
  const slow = api.buildRoute(coords, null, { distance: totalM, duration: 2 * 3600 }); // llegada a las 14:00
  const hits2 = api.buildWeatherHits(api.samplePoints(slow, 3000), list, dep);
  const sum = api.weatherSummary(hits2, dep);
  assert.equal(sum.length, 1);
  assert.match(sum[0], /^Lluvia fuerte \(8,0 mm\/h\) hacia las \d\d:\d\d \(km \d+,\d\)$/);
  const one = api.buildWeatherHits([pts[0]], rainy, dep); // un solo punto: objeto, no lista
  assert.equal(one.length, 1);
  assert.deepEqual(api.buildWeatherHits(pts, list, dep - 40 * 86400000), []); // fuera de rango
});

test('describe del tiempo', () => {
  const w = { temp: 2.6, rain: 6.2, prob: 80, snow: 0, wind: 25, gust: 72, vis: 5000, code: 65 };
  const d = api.describe({ layer: 'wx', w });
  assert.equal(d.title, 'Lluvia fuerte · 3 °C');
  assert.equal(d.sub, 'Lluvia 6,2 mm/h (80 %) · viento 25 km/h (rachas 72)');
  assert.equal(d.sev, 'high');
  assert.equal(d.text, 'Lluvia fuerte (6,2 mm/h) · Rachas de 72 km/h · Riesgo de hielo o nieve');
  const calm = api.describe({ layer: 'wx', w: { temp: 20, rain: 0, prob: null, snow: 0, wind: 10, gust: null, vis: null, code: 0 } });
  assert.equal(calm.title, 'Despejado · 20 °C');
  assert.equal(calm.sev, 'info');
  assert.equal(calm.sub, 'Lluvia 0,0 mm/h · viento 10 km/h');
});

test('samplePoints: maxPts permite muestreo más fino en rutas largas', () => {
  const fine = api.samplePoints(route, 500, 400);
  assert.ok(fine.length > 15 && fine.length <= 401);
  assert.equal(api.samplePoints(route, 500, 5).length <= 6, true); // el tope manda sobre el paso
});

test('pointInRing: dentro, fuera y polígono cóncavo', () => {
  const sq = [[36.69, -4.46], [36.71, -4.46], [36.71, -4.44], [36.69, -4.44], [36.69, -4.46]];
  assert.equal(api.pointInRing(36.70, -4.45, sq), true);
  assert.equal(api.pointInRing(36.70, -4.47, sq), false);
  const u = [[0, 0], [0, 3], [3, 3], [3, 2], [1, 2], [1, 1], [3, 1], [3, 0]]; // "C" abierta hacia el este
  assert.equal(api.pointInRing(0.5, 0.5, u), true);
  assert.equal(api.pointInRing(1.5, 1.5, u), false); // hueco de la C
});

const av = (over = {}) => ({
  id: 'A#0', ev: 'Aviso de lluvias de nivel naranja', ph: 'Lluvias', lvl: 'naranja', area: 'Litoral de prueba',
  desc: 'Precipitación acumulada en una hora: 40 mm.', from: '2026-11-16T12:20:00Z', to: '2026-11-16T13:00:00Z',
  poly: [[[36.69, -4.46], [36.71, -4.46], [36.71, -4.44], [36.69, -4.44], [36.69, -4.46]]], ...over,
});

test('buildAvisoHits: entra en el polígono, respeta la vigencia a la hora de paso', () => {
  const dep = Date.UTC(2026, 10, 16, 12);
  const pts = api.samplePoints(route, 500, 400);
  const hits = api.buildAvisoHits(pts, [
    av(),                                                         // vigente cuando se pasa por la zona (12:24–12:36)
    av({ id: 'B#0', from: '2026-11-16T12:00:00Z', to: '2026-11-16T12:10:00Z' }), // caduca antes de llegar
    av({ id: 'C#0', from: '2026-11-16T13:30:00Z', to: '2026-11-16T14:00:00Z' }), // empieza después
    av({ id: 'D#0', poly: [[[37.5, -4.46], [37.6, -4.46], [37.6, -4.44], [37.5, -4.44]]] }), // zona lejana
  ], dep);
  assert.deepEqual(hits.map((h) => h.item.id), ['A#0']);
  const h = hits[0];
  assert.equal(h.layer, 'avi');
  assert.ok(h.s > totalM * 0.38 && h.s < totalM * 0.5);
  assert.ok(h.sEnd > h.s && h.sEnd < totalM * 0.62);
  assert.deepEqual(api.buildAvisoHits(pts, [], dep), []);
  assert.deepEqual(api.buildAvisoHits(pts, undefined, dep), []);
});

test('avisoSummary y describe de avisos', () => {
  const dep = Date.UTC(2026, 10, 16, 12);
  const hits = api.buildAvisoHits(api.samplePoints(route, 500, 400), [av(), av({ id: 'E#0', lvl: 'amarillo', ph: 'Viento' })], dep);
  const lines = api.avisoSummary(hits);
  assert.equal(lines.length, 2);
  assert.match(lines[0], /^Aviso naranja: lluvias en Litoral de prueba \(km \d+,\d–\d+,\d, hasta las \d\d:\d\d\)$/);
  assert.equal(api.avisoSummary(hits, 1).length, 2);
  assert.equal(api.avisoSummary(hits, 1)[1], 'y 1 aviso(s) más de AEMET');
  const d = api.describe(hits[0]);
  assert.equal(d.title, 'Aviso de lluvias de nivel naranja');
  assert.match(d.sub, /^Litoral de prueba · hasta las \d\d:\d\d$/);
  assert.equal(d.sev, 'high');
  assert.equal(api.describe({ layer: 'avi', item: av({ lvl: 'amarillo' }) }).sev, 'mid');
});

test('calidadResumen y marca de fin previsto vencido', () => {
  assert.equal(api.calidadResumen(null), null);
  assert.equal(api.calidadResumen({}), null);
  const cal = {
    nivel: 'media', window_h: 24, motivos: ['incidencias: hueco de 124 min entre ejecuciones'],
    feeds: { incidencias: { lag_p50_s: 42, ok_pct: 100 } },
    dato: { incidencias: { caducadas: 6 }, paneles: { sin_localizacion: 2 } },
  };
  const q = api.calidadResumen(cal);
  assert.equal(q.nivel, 'media');
  assert.deepEqual(q.detalle, ['retraso típico del feed 42 s', '100 % de descargas correctas en 24 h']);
  assert.deepEqual(q.avisos, ['incidencias: hueco de 124 min entre ejecuciones', '6 incidencias con fin previsto vencido', '2 paneles sin localización (no se pueden situar)']);
  const base = { id: '1', types: ['roadworks'], road: 'N-332', a: [38.7, 0.1] };
  assert.match(api.describe({ layer: 'inc', item: { ...base, end: '2020-01-01T00:00:00Z' } }).sub, /fin previsto vencido/);
  assert.doesNotMatch(api.describe({ layer: 'inc', item: { ...base, end: '2999-01-01T00:00:00Z' } }).sub, /vencido/);
  assert.doesNotMatch(api.describe({ layer: 'inc', item: base }).sub, /vencido/);
});

test('collectCharge: potencia mínima, buffer amplio y descripción', () => {
  const wide = api.buildRoute(coords, null, { distance: totalM, duration: 3600 }, 1500, 1500);
  const items = [
    { id: 'a', lat: offsetLat(900), lon: -4.45, kw: 150, n: 4, op: 'Iberdrola', con: ['iec62196T2COMBO', 'chademo'], dc: true, h24: true, addr: 'Calle Mayor 1', mun: 'Málaga' },
    { id: 'b', lat: offsetLat(900), lon: -4.45, kw: 22, n: 2 },                 // lenta: fuera
    { id: 'c', lat: offsetLat(5000), lon: -4.45, kw: 150, n: 1 },               // lejos: fuera
    { id: 'd', lat: offsetLat(0), lon: -4.42, kw: 50, n: 1, con: ['otro'] },     // justo en el mínimo
    { id: 'e', lat: offsetLat(0), lon: -4.43 },                                  // sin potencia: fuera
  ];
  const hits = api.collectCharge(wide, items);
  assert.deepEqual(hits.map((h) => h.item.id), ['a', 'd']);
  assert.ok(hits[0].s < hits[1].s && hits[0].dist > 850 && hits[0].dist < 950);
  assert.equal(api.nearest(route, offsetLat(900), -4.45), null); // con el índice normal (150 m) no entraría
  const d = api.describe(hits[0]);
  assert.equal(d.title, 'Carga 150 kW · Iberdrola');
  assert.equal(d.sub, 'CCS, CHAdeMO · 4 puntos · 24 h · a 900 m de la ruta');
  assert.equal(d.text, 'Calle Mayor 1, Málaga');
  assert.equal(api.describe(hits[1]).sub, 'otro · 1 punto · a 0 m de la ruta');
  assert.deepEqual(api.collectCharge(wide, undefined), []);
});

test('collectRisk: tramos cerca de la ruta y aviso de poca muestra', () => {
  const wide = api.buildRoute(coords, null, { distance: totalM, duration: 3600 }, 1500, 1500);
  const doc = { days: 3, reliable_days: 30, items: [
    { road: 'A-7', pk: 100, n: 4, acc: 2, score: 9, last: '2026-11-15', lat: offsetLat(300), lon: -4.45 },
    { road: 'A-7', pk: 140, n: 3, acc: 0, score: 3, last: '2026-11-14', lat: offsetLat(1200), lon: -4.45 }, // dentro del índice pero a >400 m
    { road: 'N-340', pk: 5, n: 3, acc: 0, score: 3, last: '2026-11-10', lat: offsetLat(9000), lon: -4.45 },
  ] };
  const hits = api.collectRisk(wide, doc);
  assert.equal(hits.length, 1);
  const d = api.describe(hits[0]);
  assert.equal(d.title, 'Tramo con incidencias repetidas · A-7');
  assert.equal(d.sub, 'PK 100–101 · 4 incidencias (2 accidentes) · última 2026-11-15');
  assert.equal(d.text, 'Solo 3 días de histórico: poco fiable');
  assert.equal(d.sev, 'mid');
  const ok = api.describe(api.collectRisk(wide, { ...doc, days: 45 })[0]);
  assert.equal(ok.text, 'Histórico de 45 días');
  assert.deepEqual(api.collectRisk(wide, null), []);
});

test('simplifyLine conserva extremos y forma, y respeta el máximo', () => {
  const small = [[36.7, -4.5], [36.70001234, -4.4]];
  assert.deepEqual(api.simplifyLine(small), [[36.7, -4.5], [36.70001, -4.4]]);
  // 2000 puntos con una curva en "L": debe quedarse con muy pocos y conservar la esquina
  const ll = [];
  for (let i = 0; i <= 1000; i++) ll.push([36.7, -4.5 + i * 0.0001]);
  for (let i = 1; i <= 1000; i++) ll.push([36.7 + i * 0.0001, -4.4]);
  const s = api.simplifyLine(ll, 50);
  assert.ok(s.length <= 50 && s.length >= 3);
  assert.deepEqual(s[0], [36.7, -4.5]);
  assert.deepEqual(s[s.length - 1], [36.8, -4.4]);
  assert.ok(s.some((p) => Math.abs(p[0] - 36.7) < 1e-6 && Math.abs(p[1] + 4.4) < 1e-6)); // la esquina
  // ruido en zigzag: con tope bajo sigue devolviendo <= tope
  const zig = Array.from({ length: 3000 }, (_, i) => [36.7 + (i % 2) * 0.0003, -4.5 + i * 0.00003]);
  assert.ok(api.simplifyLine(zig, 100).length <= 100);
});

test('nextDeparture: días ISO, hora local y margen de 15 min', () => {
  const c = { d: [1, 2, 3, 4, 5], h: '07:30' };
  const lun = new Date(2026, 10, 16, 6, 50).getTime(); // lunes
  assert.equal(api.nextDeparture(c, lun), new Date(2026, 10, 16, 7, 30).getTime());
  assert.equal(api.nextDeparture(c, new Date(2026, 10, 16, 7, 40).getTime()), new Date(2026, 10, 16, 7, 30).getTime()); // aún dentro de margen
  assert.equal(api.nextDeparture(c, new Date(2026, 10, 16, 8, 0).getTime()), new Date(2026, 10, 17, 7, 30).getTime());  // ya pasó: mañana
  assert.equal(api.nextDeparture(c, new Date(2026, 10, 20, 9, 0).getTime()), new Date(2026, 10, 23, 7, 30).getTime()); // viernes tarde -> lunes
  assert.equal(api.nextDeparture({ d: [7], h: '10:00' }, lun), new Date(2026, 10, 22, 10, 0).getTime()); // domingo = 7
  assert.equal(api.nextDeparture({ d: [], h: '10:00' }, lun), null);
  assert.equal(api.nextDeparture({ d: [1], h: 'xx' }, lun), null);
});

test('corridorsExport y fmtDays', () => {
  const c = { n: 'A → B', d: [1, 2], h: '07:30', l: [[1, 2], [3, 4]], dur: 3600.4, dist: 8900.6, o: { name: 'secreto' }, dd: { name: 'secreto' } };
  const out = JSON.parse(api.corridorsExport([c]));
  assert.deepEqual(out, { v: 1, corredores: [{ n: 'A → B', d: [1, 2], h: '07:30', l: [[1, 2], [3, 4]], dur: 3600, dist: 8901 }] });
  assert.ok(!JSON.stringify(out).includes('secreto')); // no se exportan los nombres de los lugares
  assert.equal(api.fmtDays([5, 4, 3, 2, 1]), 'L-V');
  assert.equal(api.fmtDays([1, 2, 3, 4, 5, 6, 7]), 'todos los días');
  assert.equal(api.fmtDays([6, 1]), 'L S');
});

// ---- modo conducción: anuncios a 5 km, sin repetir, por gravedad, y salida de ruta
const km = (k) => k * 1000;
const lonAt = (m) => -4.5 + (m / totalM) * 0.1; // lon del punto a m metros del origen
const inc = (id, types, m, extra = {}) => ({ layer: 'inc', s: m, t: 0, item: { id, types, road: 'A-7', pk: [10], ...extra } });
const rad = (id, m) => ({ layer: 'rad', s: m, t: 0, item: { id, road: 'A-7', pk: [12] } });
const wxHit = (m, rain) => ({ layer: 'wx', s: m, t: 0, w: { rain, wind: 10, gust: 20, prob: 80, temp: 12, code: 63, vis: 20000, snow: 0 } });

test('anuncia solo lo que queda por delante a menos de 5 km', () => {
  const hits = [inc('a', ['accident'], km(2)), inc('b', ['accident'], km(8)), inc('c', ['accident'], 100)];
  const r1 = api.driveStep(route, hits, LAT, lonAt(500), new Set());
  assert.equal(r1.off, false);
  assert.equal(r1.say.length, 1); // 'c' (100 m) ya queda atrás y 'b' (8 km) aún está lejos
});

test('prioriza lo grave y respeta el máximo por lectura', () => {
  const hits = [rad('r', km(1)), inc('g', ['accident'], km(4)), inc('o', ['roadworks'], km(2))];
  const r = api.driveStep(route, hits, LAT, lonAt(0), new Set(), 5000, 2);
  assert.equal(r.say.length, 2);
  assert.match(r.say[0].text, /accidente/i);
});

test('una vez dicho no se repite y al avanzar entra el siguiente', () => {
  const hits = [inc('a', ['accident'], km(2)), inc('b', ['accident'], km(7))];
  const said = new Set();
  const r1 = api.driveStep(route, hits, LAT, lonAt(0), said);
  r1.say.forEach((x) => said.add(x.key));
  assert.equal(r1.say.length, 1);
  assert.equal(api.driveStep(route, hits, LAT, lonAt(0), said).say.length, 0);
  const r2 = api.driveStep(route, hits, LAT, lonAt(km(3)), said);
  assert.equal(r2.say.length, 1);
});

test('del tiempo solo se dice lo adverso y lo ya pasado no se dice', () => {
  const hits = [wxHit(km(1), 0), wxHit(km(2), 8), inc('p', ['accident'], km(1))];
  const r = api.driveStep(route, hits, LAT, lonAt(0), new Set(), 5000, 5);
  assert.equal(r.say.length, 2); // accidente y lluvia fuerte; la lluvia 0 no
  assert.ok(r.say.every((x) => !/Lluvia 0,0/.test(x.text)));
  assert.equal(api.driveStep(route, hits, LAT, lonAt(km(2.5)), new Set(), 5000, 5).say.length, 0); // todo queda atrás
});

test('fuera de la ruta no anuncia nada', () => {
  const r = api.driveStep(route, [inc('a', ['accident'], km(2))], offsetLat(2000), lonAt(0), new Set());
  assert.equal(r.off, true);
  assert.equal(r.say.length, 0);
});

test('frase en español con distancia', () => {
  assert.match(api.driveSpeech(4800, { title: 'Accidente', sub: 'A-7 · PK 10,0', text: '' }), /^En 5 kilómetros\. Accidente\. A-7 , punto kilométrico 10,0/);
  assert.match(api.driveSpeech(600, { title: 'Radar fijo', sub: '', text: '' }), /^En 600 metros\. Radar fijo/);
});
