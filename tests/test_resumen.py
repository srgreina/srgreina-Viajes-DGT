"""Tests de resumen.py con histórico simulado (sin red)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

import resumen as r  # noqa: E402

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
LAT = 36.7
LINE = [[LAT, -4.5 + i * 0.01] for i in range(11)]
COR = {"n": "Casa → Obra", "l": LINE, "dur": 3600, "dist": 8900}


def ev(kind, i, t, **kw):
    d = {"t": t, "ev": kind, "id": i}
    d.update(kw)
    return d


def write(tmp, day, events):
    os.makedirs(os.path.join(tmp, "incidencias"), exist_ok=True)
    with open(os.path.join(tmp, "incidencias", day + ".jsonl"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(e) for e in events))


class Resumen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        geo = {"autonomousCommunity": "Andalucía"}
        write(self.tmp, "2026-11-14", [
            ev("open", "1", "2026-11-14T08:00:00Z", types=["accident", "carriagewayClosures"], road="A-92", a=[LAT, -4.45], geo=geo, start="2026-11-14T08:00:00Z"),
            ev("close", "1", "2026-11-14T10:00:00Z"),                                   # 2 h, en el corredor
            ev("open", "2", "2026-11-14T09:00:00Z", types=["roadClosed", "roadworks"], road="A-7", a=[40.0, -3.0], geo=geo, start="2026-11-14T09:00:00Z"),
            ev("close", "2", "2026-11-14T10:30:00Z"),                                   # 1,5 h, obras, fuera del corredor
            ev("open", "3", "2026-11-14T09:00:00Z", types=["accident"], road="A-92", a=[LAT, -4.45], geo=geo),  # no es corte
            ev("open", "4", "2026-11-14T09:00:00Z", types=["roadClosed"], road="M-30", a=[40.4, -3.7], geo={"autonomousCommunity": "Madrid"}, start="2026-11-14T09:00:00Z"),
            ev("close", "4", "2026-11-14T11:00:00Z"),                                   # otra comunidad
        ])
        write(self.tmp, "2026-11-16", [
            ev("open", "5", "2026-11-16T10:00:00Z", types=["roadClosed"], road="A-92", a=[LAT, -4.4], geo=geo, start="2026-11-16T10:00:00Z"),  # sigue abierto: 2 h hasta NOW
        ])
        self.cuts = r.load_cuts(self.tmp, NOW)

    def test_solo_cortes(self):
        self.assertEqual(sorted(c["road"] for c in self.cuts), ["A-7", "A-92", "A-92", "M-30"])

    def test_duracion_y_abiertos(self):
        and_a92 = [c for c in self.cuts if c["road"] == "A-92"]
        self.assertAlmostEqual(r.hours(and_a92), 4.0)

    def test_resumen_andalucia(self):
        title, body = r.build(self.cuts, [])
        self.assertIn("Andalucía: 2 cortes · 4,0 h (+1 por obras en curso)", body)
        self.assertIn("A-92: 2 · 4,0 h · sigue cortado", body)
        self.assertNotIn("M-30", body)

    def test_corredor(self):
        _, body = r.build(self.cuts, [COR])
        self.assertIn("Casa → Obra: 2 cortes · 4,0 h", body)

    def test_corredor_sin_cortes(self):
        lejos = dict(COR, l=[[41.0, -4.5 + i * 0.01] for i in range(11)])
        _, body = r.build(self.cuts, [lejos])
        self.assertIn("Casa → Obra: sin cortes imprevistos", body)

    def test_sin_historico(self):
        self.assertEqual(r.load_cuts(tempfile.mkdtemp(), NOW), [])
        self.assertIn("Andalucía: sin cortes imprevistos", r.build([], [])[1])


if __name__ == "__main__":
    unittest.main()
