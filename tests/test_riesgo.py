"""Tests de riesgo.py con eventos sintéticos."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

from riesgo import build, days_covered, fold_day, update, weight  # noqa: E402


def ev(i, types, road="A-7", pk=(123.4, 123.6), a=(36.7, -4.4), sit=None, **kw):
    return {"ev": "open", "t": "2026-11-16T10:00:00Z", "id": str(i), "sit": sit or f"s{i}", "types": types,
            "road": road, "pk": list(pk), "a": list(a), **kw}


class RiesgoTests(unittest.TestCase):
    def test_pesos(self):
        self.assertEqual(weight(["roadworks", "laneClosures"]), 0)  # planificado
        self.assertEqual(weight(["vehicleObstruction", "vehicleStuck"]), 1)
        self.assertEqual(weight(["accident", "vehicleStuck"]), 3)  # máximo, no suma
        self.assertEqual(weight(None), 0)

    def test_fold_ignora_boot_obras_y_sin_posicion_y_dedupe_por_situacion(self):
        bins = {}
        fold_day(bins, [
            ev(1, ["accident"]),
            ev(2, ["vehicleStuck"], sit="s1"),                      # misma situación y tramo: no suma
            ev(3, ["vehicleStuck"]),
            ev(4, ["roadworks"]),                                    # planificada
            ev(5, ["accident"], boot=True),                          # foto inicial, no es un suceso nuevo
            ev(6, ["accident"], road=None),                          # sin vía
            ev(7, ["accident"], pk=()),                              # sin PK
            {**ev(8, ["accident"]), "ev": "close"},
            ev(9, ["accident"], pk=(124.1, 124.2)),                  # otro tramo de 1 km
        ])
        self.assertEqual(sorted(bins), ["A-7|123", "A-7|124"])
        b = bins["A-7|123"]
        self.assertEqual((b["n"], b["s"], b["acc"]), (2, 4, 1))

    def test_build_umbral_y_orden(self):
        bins = {}
        for d in range(3):
            fold_day(bins, [ev(100 + d, ["accident"])])  # tramo A-7|123: n=3, score 9
        for d in range(3):
            fold_day(bins, [ev(200 + d, ["vehicleStuck"], road="N-340", pk=(10.2, 10.3), a=(37, -5))])  # n=3, score 3
        fold_day(bins, [ev(300, ["accident"], road="AP-7", pk=(5, 6))])  # n=1: no llega al umbral
        items = build({"bins": bins})
        self.assertEqual([(i["road"], i["pk"], i["n"], i["score"], i["acc"]) for i in items],
                         [("A-7", 123, 3, 9, 3), ("N-340", 10, 3, 3, 0)])
        self.assertEqual((items[0]["lat"], items[0]["lon"]), (36.7, -4.4))

    def test_update_incremental_solo_dias_completos(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {}
            for day in ("2026-11-14", "2026-11-15", "2026-11-16"):
                p = os.path.join(tmp, day + ".jsonl")
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev(day, ["accident"], sit="s" + day)) + "\n")
                files[day] = p
            st = update({"first": None, "through": None, "bins": {}}, files, "2026-11-16")  # hoy no cuenta
            self.assertEqual((st["first"], st["through"], days_covered(st)), ("2026-11-14", "2026-11-15", 2))
            self.assertEqual(st["bins"]["A-7|123"]["n"], 2)
            update(st, files, "2026-11-16")  # repetir no duplica
            self.assertEqual(st["bins"]["A-7|123"]["n"], 2)
            update(st, files, "2026-11-17")  # al día siguiente entra el 16
            self.assertEqual((st["through"], st["bins"]["A-7|123"]["n"], days_covered(st)), ("2026-11-16", 3, 3))
        self.assertEqual(days_covered({"first": None, "through": None}), 0)


if __name__ == "__main__":
    unittest.main()
