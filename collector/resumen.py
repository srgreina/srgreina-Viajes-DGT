"""Resumen semanal de cortes: lo que se ha cortado en la última semana en Andalucía y en tus corredores (ntfy.sh).

  NTFY_TOPIC=... CORREDORES='{"v":1,"corredores":[...]}' python collector/resumen.py --history data/history

- Sale del histórico de incidencias (data/history/incidencias/AAAA-MM-DD.jsonl, días UTC): une open/change/close por
  id y cuenta como corte lo que lleva `roadClosed` o `carriagewayClosures`. Los de obras (roadworks) se cuentan aparte y no entran en el ranking. Duración = de su inicio (recortado a la
  ventana) al cierre, o hasta ahora si sigue abierto.
- Sin NTFY_TOPIC imprime el resumen y no envía nada; con él solo imprime recuentos (los logs de Actions son públicos). Sin CORREDORES solo lleva la parte de Andalucía.
- Los corredores son privados (el repo es público): solo se leen del secreto, nunca de un fichero.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import now_utc, parse_dt  # noqa: E402
from corredores import make_route, nearest, nearest_line, send_ntfy  # noqa: E402

CLOSE_TYPES = {"roadClosed", "carriagewayClosures"}
PLANNED_TYPES = {"roadworks", "roadMaintenance"}
DAYS = 7
REGION = "Andalucía"


def load_cuts(history_dir, now, days=DAYS):
    """Devuelve [{road, a, b, region, start, end, planned}] de los cortes que tocan la ventana [now-days, now]."""
    win_start = now - timedelta(days=days)
    recs = {}
    for k in range(days + 1):
        day = (win_start + timedelta(days=k)).strftime("%Y-%m-%d")
        path = os.path.join(history_dir, "incidencias", day + ".jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                t = parse_dt(ev.get("t"))
                if not t or not ev.get("id"):
                    continue
                if ev.get("ev") in ("open", "change"):
                    r = recs.setdefault(ev["id"], {"seen": t, "closed": None})
                    r.update({"rec": ev})
                    r["closed"] = None  # reabierta
                elif ev.get("ev") == "close" and ev["id"] in recs:
                    recs[ev["id"]]["closed"] = t
    cuts = []
    for r in recs.values():
        ev = r.get("rec") or {}
        types = set(ev.get("types") or [])
        if not types & CLOSE_TYPES:
            continue
        start = max(parse_dt(ev.get("start")) or r["seen"], win_start)
        end = min(r["closed"] or now, now)
        if end <= start:
            continue
        cuts.append({
            "road": ev.get("road") or "sin carretera", "a": ev.get("a"), "b": ev.get("b"),
            "region": (ev.get("geo") or {}).get("autonomousCommunity"),
            "start": start, "end": end, "planned": bool(types & PLANNED_TYPES), "open": r["closed"] is None,
        })
    return cuts


def hours(cuts):
    return sum((c["end"] - c["start"]).total_seconds() for c in cuts) / 3600


def fmt_h(h):
    return (f"{h:.1f}".replace(".", ",") if h < 10 else f"{h:.0f}") + " h"


def by_road(cuts, top=5):
    acc = defaultdict(list)
    for c in cuts:
        acc[c["road"]].append(c)
    ranked = sorted(acc.items(), key=lambda kv: (-hours(kv[1]), kv[0]))[:top]
    return [f"{road}: {len(v)} · {fmt_h(hours(v))}" + (" · sigue cortado" if any(c["open"] for c in v) else "") for road, v in ranked]


def on_corridor(corridor, cut):
    route = make_route(corridor["l"], corridor.get("dur") or 1, corridor.get("dist") or 1)
    if not cut["a"]:
        return False
    if cut["b"]:
        return nearest_line(route, cut["a"], cut["b"]) is not None
    return nearest(route, *cut["a"]) is not None


def line(label, cuts, top):
    """Los cortes por obras (largos y previstos) no entran en el ranking: se cuentan aparte."""
    real = [c for c in cuts if not c["planned"]]
    obras = len(cuts) - len(real)
    extra = f" (+{obras} por obras en curso)" if obras else ""
    if not real:
        return [f"{label}: sin cortes imprevistos{extra}"]
    return [f"{label}: {len(real)} cortes · {fmt_h(hours(real))}{extra}"] + ["  " + x for x in by_road(real, top)]


def build(cuts, corridors):
    """Devuelve (título, cuerpo)."""
    lines = line(REGION, [c for c in cuts if c["region"] == REGION], 5)
    for cor in corridors:
        try:
            lines += line(cor.get("n") or "Corredor", [c for c in cuts if on_corridor(cor, c)], 2)
        except Exception as exc:  # noqa: BLE001 - un corredor malo no frena el resto ni revela datos
            print(f"resumen: error en un corredor ({type(exc).__name__})", file=sys.stderr)
    return "Resumen semanal de cortes", "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="data/history")
    args = ap.parse_args()
    corridors = []
    raw = os.environ.get("CORREDORES", "").strip()
    if raw:
        try:
            corridors = json.loads(raw).get("corredores", [])
        except ValueError:
            print("resumen: el secreto CORREDORES no es un JSON válido; solo se incluye Andalucía", file=sys.stderr)
    title, body = build(load_cuts(args.history, now_utc()), corridors)
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if topic:
        # El log de Actions es público: con tema de ntfy solo se imprimen recuentos (el contenido puede llevar nombres de corredores)
        send_ntfy(topic, title, body, priority=3)
        print(f"resumen: enviado ({len(corridors)} corredores)")
    else:
        print(title + "\n" + body)
        print("resumen: sin NTFY_TOPIC, no se envía")
    return 0


if __name__ == "__main__":
    sys.exit(main())
