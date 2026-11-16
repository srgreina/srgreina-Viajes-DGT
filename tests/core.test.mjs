// Prueba la lógica pura del planificador: extrae el bloque <core> de docs/index.html.
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../docs/index.html', import.meta.url), 'utf8');
const core = html.slice(html.indexOf('// <core>'), html.indexOf('// </core>'));
const api = new Function(
  `${core}; return { buildRoute, nearest, nearestLine, collectHits, describe, fmtDur, fmtKm, fmtPk };`,
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
