"""Tests de calidad.py con datos sintéticos."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

from calidad import compute, feed_stats, percentile, reliability  # noqa: E402

NOW = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)


def run(feed, minutes_ago, ok=True, lag=40):
    t = (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = {"t": t, "feed": feed, "ok": ok}
    if ok:
        r["lag_s"] = lag
    return r


def rows(minutes, **kw):
    return [r for m in minutes for f in ("incidencias", "paneles") for r in [run(f, m, **kw)]]


class CalidadTests(unittest.TestCase):
    def test_percentil(self):
        self.assertIsNone(percentile([], 0.5))
        self.assertEqual(percentile([10, 20, 30, 40], 0.5), 25)
        self.assertEqual(percentile([5], 0.95), 5)

    def test_feed_stats(self):
        rs = [run("incidencias", 60), run("incidencias", 50, ok=False), run("incidencias", 10, lag=100),
              run("paneles", 5), run("incidencias", 48 * 60)]  # la última queda fuera de la ventana
        s = feed_stats(rs, "incidencias", NOW)
        self.assertEqual((s["runs"], s["ok_pct"], s["gap_max_min"], s["since_last_ok_min"]), (3, 66.7, 40, 10))
        self.assertEqual(s["lag_p95_s"], 97)
        self.assertEqual(feed_stats([], "incidencias", NOW), {"runs": 0})

    def test_semaforo(self):
        buena = compute(rows([30, 20, 10]), {"items": []}, {"items": []}, set(), NOW)
        self.assertEqual((buena["nivel"], buena["motivos"]), ("buena", []))
        hueco = compute(rows([200, 100, 10]), {"items": []}, {"items": []}, set(), NOW)
        self.assertEqual(hueco["nivel"], "media")
        self.assertIn("hueco de 100 min", hueco["motivos"][0])
        parado = compute(rows([300, 200, 100]), {"items": []}, {"items": []}, set(), NOW)
        self.assertEqual(parado["nivel"], "baja")
        self.assertEqual(reliability({"incidencias": {"runs": 0}})[0], "baja")
        lento = compute(rows([30, 20, 10], lag=1000), {"items": []}, {"items": []}, set(), NOW)
        self.assertEqual(lento["nivel"], "baja")

    def test_calidad_del_dato(self):
        inc = {"generated": "2026-11-16T12:00:00Z", "items": [
            {"id": "1", "a": [1, 2], "road": "A-7", "end": "2026-11-16T11:00:00Z"},   # caducada respecto a generated
            {"id": "2", "a": [1, 2], "road": "A-7", "end": "2026-11-16T13:00:00Z"},   # vigente cuando se generó
            {"id": "3", "road": ""},                                                    # sin coordenadas ni vía
            {"id": "4", "a": [1, 2], "road": "N-340"},
        ]}
        pan = {"items": [{"id": "c.1", "ctrl": "c"}, {"id": "d.1", "ctrl": "d"}]}
        d = compute(rows([20, 10]), inc, pan, {"c"}, NOW)["dato"]
        self.assertEqual((d["incidencias"]["total"], d["incidencias"]["caducadas"]), (4, 1))
        self.assertEqual((d["incidencias"]["sin_coord_pct"], d["incidencias"]["sin_via_pct"]), (25.0, 25.0))
        self.assertEqual((d["paneles"]["sin_localizacion"], d["paneles"]["sin_localizacion_pct"]), (1, 50.0))
        self.assertIsNone(compute(rows([20, 10]), inc, pan, None, NOW)["dato"]["paneles"]["sin_localizacion"])


if __name__ == "__main__":
    unittest.main()
