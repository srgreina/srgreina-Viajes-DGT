"""Tramos de riesgo: dónde se repiten las incidencias NO planificadas (accidentes, averías, objetos en calzada...).

  python collector/riesgo.py --history data/history --out data/static

Es incremental: el acumulado por tramo de 1 km (carretera + PK) vive en data/history/riesgo_estado.json y cada
ejecución solo procesa los días COMPLETOS (UTC) que aún no ha visto; así no relee todo el histórico.
Salida: data/static/riesgo.json con los tramos que acumulan >= MIN_N incidencias distintas.

Cuenta solo eventos `open` que no son del arranque (`boot`), una vez por situación (`sit`) y día, con el peso máximo
de sus tipos. Las obras y cortes planificados no cuentan. La fiabilidad depende de los días acumulados: el planificador
avisa si hay menos de RELIABLE_DAYS.
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import iso, now_utc, read_json, write_json  # noqa: E402

WEIGHTS = {
    "accident": 3, "vehicleOnFire": 3,
    "rockfalls": 2, "shedLoad": 2, "spillageOnTheRoad": 2, "forestFire": 2, "avalanches": 2, "flooding": 2,
    "vehicleStuck": 1, "objectOnTheRoad": 1, "obstructionOnTheRoad": 1, "slowTraffic": 1, "abnormalTraffic": 1,
}
MIN_N = 3
RELIABLE_DAYS = 30


def weight(types):
    return max((WEIGHTS.get(t, 0) for t in types or []), default=0)


def bin_key(ev):
    pk = ev.get("pk") or []
    if not ev.get("road") or not pk or not ev.get("a"):
        return None
    return f"{ev['road']}|{int(min(pk))}"


def fold_day(bins, events):
    """Suma al acumulado los `open` (no boot) de un día; una vez por situación."""
    seen = set()
    for ev in events:
        if ev.get("ev") != "open" or ev.get("boot"):
            continue
        w = weight(ev.get("types"))
        key = bin_key(ev)
        if not w or not key:
            continue
        sid = ev.get("sit") or ev.get("id")
        if (sid, key) in seen:
            continue
        seen.add((sid, key))
        b = bins.setdefault(key, {"n": 0, "s": 0, "acc": 0, "lat": 0.0, "lon": 0.0, "last": ""})
        b["n"] += 1
        b["s"] += w
        b["acc"] += 1 if "accident" in (ev.get("types") or []) else 0
        b["lat"] += ev["a"][0]
        b["lon"] += ev["a"][1]
        b["last"] = max(b["last"], (ev.get("t") or "")[:10])


def build(state):
    items = []
    for key, b in state["bins"].items():
        if b["n"] < MIN_N:
            continue
        road, pk = key.rsplit("|", 1)
        items.append({
            "road": road, "pk": int(pk), "n": b["n"], "acc": b["acc"], "score": b["s"],
            "lat": round(b["lat"] / b["n"], 5), "lon": round(b["lon"] / b["n"], 5), "last": b["last"],
        })
    items.sort(key=lambda i: (-i["score"], i["road"], i["pk"]))
    return items


def days_covered(state):
    if not state.get("first") or not state.get("through"):
        return 0
    d0 = datetime.fromisoformat(state["first"])
    d1 = datetime.fromisoformat(state["through"])
    return (d1 - d0).days + 1


def update(state, day_files, today):
    """day_files: {'AAAA-MM-DD': ruta}. Procesa los días completos posteriores a state['through']."""
    for day in sorted(day_files):
        if day >= today or (state.get("through") and day <= state["through"]):
            continue
        events = []
        with open(day_files[day], encoding="utf-8") as fh:
            for line in fh:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
        fold_day(state["bins"], events)
        state["first"] = state.get("first") or day
        state["through"] = day
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="data/history")
    ap.add_argument("--out", default="data/static")
    args = ap.parse_args()
    now = now_utc()
    today = now.strftime("%Y-%m-%d")
    state_path = os.path.join(args.history, "riesgo_estado.json")
    state = read_json(state_path) or {"first": None, "through": None, "bins": {}}
    files = {os.path.basename(f)[:-6]: f for f in glob.glob(os.path.join(args.history, "incidencias", "*.jsonl"))}
    before = state.get("through")
    update(state, files, today)
    if state.get("through") != before:
        write_json(state_path, state)
    items = build(state)
    write_json(os.path.join(args.out, "riesgo.json"), {
        "generated": iso(now), "days": days_covered(state), "reliable_days": RELIABLE_DAYS,
        "min_n": MIN_N, "through": state.get("through"), "count": len(items), "items": items,
    })
    print(f"riesgo: {days_covered(state)} días acumulados, {len(items)} tramos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
