"""Tests de limpieza.py sobre un histórico simulado."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

import limpieza as l  # noqa: E402

NOW = datetime(2026, 11, 22, 21, 30, tzinfo=timezone.utc)  # domingo


def touch(root, *parts):
    p = os.path.join(root, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write("{}\n")
    return p


class Limpieza(unittest.TestCase):
    def setUp(self):
        self.h = tempfile.mkdtemp()
        for d in ("2026-11-10", "2026-11-13", "2026-11-14", "2026-11-20"):
            touch(self.h, "incidencias", d + ".jsonl")
            touch(self.h, "paneles", d + ".jsonl")
        for m in ("2026-08", "2026-09", "2026-10", "2026-11"):
            touch(self.h, "runs", m + ".jsonl")

    def state(self, through):
        json.dump({"through": through, "bins": {}}, open(os.path.join(self.h, "riesgo_estado.json"), "w"))

    def names(self, files):
        return sorted(os.path.relpath(f, self.h) for f in files)

    def test_borra_mas_de_8_dias_si_riesgo_lo_proceso(self):
        self.state("2026-11-21")
        got = self.names(l.plan(self.h, NOW))
        self.assertIn("incidencias/2026-11-10.jsonl", got)
        self.assertIn("incidencias/2026-11-13.jsonl", got)
        self.assertNotIn("incidencias/2026-11-14.jsonl", got)  # justo 8 días: se conserva
        self.assertNotIn("incidencias/2026-11-20.jsonl", got)
        self.assertIn("paneles/2026-11-13.jsonl", got)

    def test_conserva_incidencias_sin_procesar(self):
        self.state("2026-11-11")
        got = self.names(l.plan(self.h, NOW))
        self.assertIn("incidencias/2026-11-10.jsonl", got)
        self.assertNotIn("incidencias/2026-11-13.jsonl", got)  # riesgo aún no llega
        self.assertIn("paneles/2026-11-13.jsonl", got)         # los paneles no dependen de riesgo

    def test_sin_estado_de_riesgo_no_borra_incidencias(self):
        got = self.names(l.plan(self.h, NOW))
        self.assertFalse([g for g in got if g.startswith("incidencias/")])

    def test_runs_conserva_mes_actual_y_anterior(self):
        got = self.names(l.plan(self.h, NOW))
        self.assertEqual([g for g in got if g.startswith("runs/")], ["runs/2026-08.jsonl", "runs/2026-09.jsonl"])

    def test_no_toca_el_estado(self):
        self.state("2026-11-21")
        self.assertNotIn("riesgo_estado.json", self.names(l.plan(self.h, NOW)))


if __name__ == "__main__":
    unittest.main()
