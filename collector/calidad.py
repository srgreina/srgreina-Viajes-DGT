"""Calidad de dato -> calidad.json (se publica en la rama `latest`).

  python collector/calidad.py --latest latest --history data/history --static data/static --out latest

Mide dos cosas, solo con lo que ya recolectamos:
  - feeds: de data/history/runs (últimas 24 h): descargas correctas, retraso de publicación (lag_s) y huecos entre ejecuciones.
  - dato: completitud del estado actual (incidencias sin coordenadas o sin vía, ya caducadas pero aún publicadas,
    paneles sin localización en paneles_loc).
Y resume en un semáforo: buena | media | baja.
"""
import argparse
import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import iso, now_utc, parse_dt, read_json, write_json  # noqa: E402

WINDOW_H = 24
FEEDS = ("incidencias", "paneles")


def pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def percentile(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo))


def read_runs(history_dir, now):
    rows = []
    months = {now.strftime("%Y-%m"), (now - timedelta(hours=WINDOW_H)).strftime("%Y-%m")}
    for m in sorted(months):
        path = os.path.join(history_dir, "runs", f"{m}.jsonl")
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            continue
    return rows


def feed_stats(rows, feed, now):
    since = now - timedelta(hours=WINDOW_H)
    mine = []
    for r in rows:
        t = parse_dt(r.get("t"))
        if r.get("feed") == feed and t and t >= since:
            mine.append((t, r))
    mine.sort(key=lambda x: x[0])
    if not mine:
        return {"runs": 0}
    ok = [(t, r) for t, r in mine if r.get("ok")]
    lags = [r["lag_s"] for _, r in ok if isinstance(r.get("lag_s"), (int, float))]
    gaps = [(b[0] - a[0]).total_seconds() / 60 for a, b in zip(mine, mine[1:])]
    last_ok = ok[-1][0] if ok else None
    return {
        "runs": len(mine),
        "ok_pct": pct(len(ok), len(mine)),
        "lag_p50_s": percentile(lags, 0.5),
        "lag_p95_s": percentile(lags, 0.95),
        "gap_max_min": round(max(gaps)) if gaps else 0,
        "last_ok": iso(last_ok) if last_ok else None,
        "since_last_ok_min": round((now - last_ok).total_seconds() / 60) if last_ok else None,
    }


def incidencias_quality(doc, now):
    items = (doc or {}).get("items") or []
    n = len(items)
    no_coord = sum(1 for i in items if not i.get("a"))
    no_road = sum(1 for i in items if not i.get("road"))
    ref = parse_dt((doc or {}).get("generated")) or now  # respecto a cuándo se generó el dato, no a "ahora"
    expired = 0
    for i in items:
        end = parse_dt(i.get("end"))
        if end and end < ref:
            expired += 1
    return {
        "total": n,
        "sin_coord_pct": pct(no_coord, n),
        "sin_via_pct": pct(no_road, n),
        "caducadas": expired,
        "caducadas_pct": pct(expired, n),
    }


def paneles_quality(doc, loc_ids):
    items = (doc or {}).get("items") or []
    n = len(items)
    no_loc = sum(1 for i in items if i.get("ctrl") not in loc_ids) if loc_ids is not None else None
    return {"total": n, "sin_localizacion": no_loc, "sin_localizacion_pct": pct(no_loc, n) if no_loc is not None else None}


def reliability(feeds):
    """buena | media | baja a partir de las estadísticas de ejecución de los feeds."""
    level = "buena"
    reasons = []
    for name, s in feeds.items():
        if not s.get("runs"):
            return "baja", [f"{name}: sin ejecuciones en {WINDOW_H} h"]
        if (s.get("since_last_ok_min") is None) or s["since_last_ok_min"] > 60 or (s.get("ok_pct") or 0) < 80 \
                or (s.get("lag_p95_s") or 0) > 900:
            return "baja", [f"{name}: datos parados o con mucho retraso"]
        if (s.get("ok_pct") or 0) < 95 or (s.get("lag_p95_s") or 0) > 300 or s.get("gap_max_min", 0) > 30:
            level = "media"
            if s.get("gap_max_min", 0) > 30:
                reasons.append(f"{name}: hueco de {s['gap_max_min']} min entre ejecuciones")
            if (s.get("ok_pct") or 0) < 95:
                reasons.append(f"{name}: {s['ok_pct']} % de descargas correctas")
            if (s.get("lag_p95_s") or 0) > 300:
                reasons.append(f"{name}: retraso p95 de {s['lag_p95_s']} s")
    return level, reasons


def compute(rows, inc_doc, pan_doc, loc_ids, now):
    feeds = {f: feed_stats(rows, f, now) for f in FEEDS}
    level, reasons = reliability(feeds)
    return {
        "generated": iso(now),
        "window_h": WINDOW_H,
        "nivel": level,
        "motivos": reasons,
        "feeds": feeds,
        "dato": {"incidencias": incidencias_quality(inc_doc, now), "paneles": paneles_quality(pan_doc, loc_ids)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default="latest")
    ap.add_argument("--history", default="data/history")
    ap.add_argument("--static", default="data/static")
    ap.add_argument("--out", default="latest")
    args = ap.parse_args()
    now = now_utc()
    loc = read_json(os.path.join(args.static, "paneles_loc.json"))
    loc_ids = {i.get("id") for i in loc["items"]} if loc and loc.get("items") else None
    doc = compute(
        read_runs(args.history, now),
        read_json(os.path.join(args.latest, "incidencias.json")),
        read_json(os.path.join(args.latest, "paneles.json")),
        loc_ids,
        now,
    )
    write_json(os.path.join(args.out, "calidad.json"), doc)
    print(f"calidad: nivel {doc['nivel']} {doc['motivos']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
