"""Tests de corredores.py con datos y envío simulados (sin red)."""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

import corredores as c  # noqa: E402

# Corredor recto de oeste a este por lat 36.70: lon -4.50 -> -4.40 (≈ 8,9 km), 1 h. Salida L-V 07:30 (Madrid, CET = UTC+1 en noviembre).
LAT = 36.7
LINE = [[LAT, -4.5 + i * 0.01] for i in range(11)]
COR = {"n": "Casa → Obra", "d": [1, 2, 3, 4, 5], "h": "07:30", "l": LINE, "dur": 3600, "dist": 8900}
MON_0650 = datetime(2026, 11, 16, 5, 50, tzinfo=timezone.utc)  # lunes 06:50 en Madrid
DEP = datetime(2026, 11, 16, 6, 30, tzinfo=timezone.utc)       # 07:30 en Madrid
off = lambda m: LAT + m / 111195  # noqa: E731

INC = {"items": [
    {"id": "1", "types": ["accident"], "road": "A-7", "a": [off(50), -4.45]},               # grave y en la ruta
    {"id": "2", "types": ["roadworks"], "road": "A-7", "a": [off(10), -4.46]},              # obras: no avisa
    {"id": "3", "types": ["roadClosed"], "road": "A-7", "a": [off(2000), -4.45]},           # lejos
    {"id": "4", "types": ["carriagewayClosures"], "a": [off(300), -4.43], "b": [off(-300), -4.43]},  # cruza, sin carretera
]}
RING = [[36.69, -4.47], [36.71, -4.47], [36.71, -4.43], [36.69, -4.43], [36.69, -4.47]]
AVI = {"items": [
    {"id": "a1", "lvl": "naranja", "ph": "Lluvias", "area": "Costa", "from": "2026-11-16T06:00:00Z", "to": "2026-11-16T09:00:00Z", "poly": [RING]},
    {"id": "a2", "lvl": "amarillo", "ph": "Viento", "area": "Costa", "from": "2026-11-16T06:00:00Z", "to": "2026-11-16T09:00:00Z", "poly": [RING]},
    {"id": "a3", "lvl": "rojo", "ph": "Nieve", "area": "Costa", "from": "2026-11-16T10:00:00Z", "to": "2026-11-16T12:00:00Z", "poly": [RING]},  # caduca/empieza fuera
]}


def wx_none(points):
    return [{"hourly": {"time": [int(DEP.timestamp())], "precipitation": [0], "temperature_2m": [15], "snowfall": [0],
                        "wind_gusts_10m": [20], "visibility": [20000], "weather_code": [1]}} for _ in points]


def wx_rain(points):
    base = wx_none(points)
    for r in base:
        r["hourly"]["precipitation"] = [8.0]
    return base


class VentanaTests(unittest.TestCase):
    def test_ventana_de_salida(self):
        self.assertEqual(c.departure_due(COR, MON_0650), DEP)
        self.assertEqual(c.departure_due(COR, MON_0650 - timedelta(hours=3)), None)          # muy pronto
        self.assertEqual(c.departure_due(COR, MON_0650 + timedelta(minutes=95)), None)       # ya pasó
        self.assertEqual(c.departure_due(COR, DEP + timedelta(minutes=10)), DEP)            # 10 min después de salir aún vale
        sab = datetime(2026, 11, 21, 5, 50, tzinfo=timezone.utc)
        self.assertEqual(c.departure_due(COR, sab), None)                                   # fin de semana
        self.assertEqual(c.departure_due({**COR, "h": "xx"}, MON_0650), None)

    def test_salida_justo_tras_medianoche(self):
        cor = {**COR, "h": "00:30", "d": [2]}  # martes 00:30; ahora lunes 23:50 Madrid = 22:50Z
        now = datetime(2026, 11, 16, 22, 50, tzinfo=timezone.utc)
        self.assertEqual(c.departure_due(cor, now), datetime(2026, 11, 16, 23, 30, tzinfo=timezone.utc))


class EvaluarTests(unittest.TestCase):
    def test_incidencias_avisos_y_tiempo(self):
        al = c.evaluate(COR, DEP, INC, AVI, wx_rain)
        keys = [a["key"] for a in al]
        self.assertIn("inc:1", keys)
        self.assertIn("inc:4", keys)
        self.assertNotIn("inc:2", keys)      # obras
        self.assertNotIn("inc:3", keys)      # lejos
        self.assertIn("avi:a1", keys)
        self.assertNotIn("avi:a2", keys)     # amarillo no se envía al móvil
        self.assertNotIn("avi:a3", keys)     # fuera de la vigencia a la hora de paso
        self.assertIn("wx:rain", keys)
        self.assertEqual([a["km"] for a in al], sorted(a["km"] for a in al))
        txt = {a["key"]: a["text"] for a in al}
        self.assertRegex(txt["inc:1"], r"^Accidente en A-7 \(km \d+, hacia las 0[78]:\d\d\)$")
        self.assertRegex(txt["inc:4"], r"^Cierre de calzada \(km \d+, hacia las 0[78]:\d\d\)$")
        self.assertRegex(txt["avi:a1"], r"^Aviso naranja: lluvias en Costa \(km \d+\)$")
        self.assertRegex(txt["wx:rain"], r"^Lluvia fuerte \(8,0 mm/h\) hacia las 0[78]:\d\d \(km \d+\)$")

    def test_sin_nada_y_tiempo_caido(self):
        self.assertEqual(c.evaluate(COR, DEP, {"items": []}, {"items": []}, wx_none), [])

        def roto(points):
            raise OSError("sin red")
        self.assertEqual([a["key"] for a in c.evaluate(COR, DEP, INC, {"items": []}, roto)], ["inc:1", "inc:4"])  # el tiempo es opcional

    def test_geometria(self):
        r = c.make_route(LINE, 3600, 8900)
        h = c.nearest(r, off(55), -4.45)
        self.assertTrue(50 < h[0] < 60 and abs(h[1] - 4450) < 40 and abs(h[2] - 1800) < 20)
        self.assertIsNone(c.nearest(r, off(600), -4.45))
        pts = c.sample_points(r, 3000)
        self.assertEqual(pts[0]["s"], 0)
        self.assertAlmostEqual(pts[-1]["s"], r["total_d"], places=3)
        self.assertTrue(c.point_in_ring(36.70, -4.45, RING) and not c.point_in_ring(36.70, -4.5, RING))


class EnvioTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.sender = lambda topic, title, body: self.sent.append((topic, title, body))

    def run_once(self, state, inc=INC, now=MON_0650, cors=(COR,)):
        return c.run(list(cors), now, inc, AVI, state, "secreto", wx_rain, self.sender)

    def test_envia_una_vez_y_reenvia_si_cambia(self):
        st, sent = self.run_once({})
        self.assertEqual(len(sent), 1)
        topic, title, body = self.sent[0]
        self.assertEqual(topic, "secreto")
        self.assertRegex(title, r"^Casa → Obra · salida 07:30: \d+ avisos$")
        self.assertIn("• Accidente en A-7", body)
        st2, sent2 = self.run_once(st)                       # misma situación: no repite
        self.assertEqual(sent2, [])
        inc2 = {"items": INC["items"] + [{"id": "9", "types": ["vehicleOnFire"], "road": "A-7", "a": [off(20), -4.42]}]}
        st3, sent3 = self.run_once(st2, inc=inc2)             # aparece algo nuevo: avisa de nuevo
        self.assertEqual(len(sent3), 1)
        self.assertEqual(len(self.sent), 2)

    def test_estado_sin_datos_personales_y_purga(self):
        old = {"sent": {"viejo": "2026-11-01T00:00:00Z"}}
        st, _ = self.run_once(old)
        self.assertNotIn("viejo", st["sent"])
        dump = json.dumps(st)
        self.assertNotIn("Casa", dump)
        self.assertNotIn("36.7", dump)

    def test_un_corredor_roto_no_frena_a_los_demas(self):
        malo = {"n": "Malo", "d": [1], "h": "07:30", "l": [], "dur": 1, "dist": 1}
        st, sent = self.run_once({}, cors=(malo, COR))
        self.assertEqual(len(sent), 1)

    def test_mensaje_largo_se_recorta(self):
        al = [{"key": str(i), "text": f"aviso {i}", "km": i, "eta": "07:00"} for i in range(9)]
        title, body = c.message(COR, DEP, al)
        self.assertIn("9 avisos", title)
        self.assertEqual(len(body.splitlines()), 7)
        self.assertTrue(body.endswith("…y 3 más"))
        self.assertIn("1 aviso", c.message(COR, DEP, al[:1])[0])
        self.assertNotIn("1 avisos", c.message(COR, DEP, al[:1])[0])


if __name__ == "__main__":
    unittest.main()
