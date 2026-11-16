"""Recolector de datos en tiempo real (incidencias y paneles).

Uso:
  python collector/realtime.py --prev prev --out latest --history data/history --samples data/samples

- Descarga cada feed, lo convierte a JSON compacto y lo escribe en --out (se publica en la rama `latest`).
- Compara con el estado anterior (--prev) y añade solo los eventos nuevos/cambiados/cerrados
  al histórico diario (JSONL). No se guardan instantáneas completas: así el repo no crece sin control.
- Registra una línea por ejecución y feed (retraso del feed, tiempo de descarga, nº de elementos),
  base de la "calidad de dato".
"""
import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from common import (  # noqa: E402
    SOURCES,
    append_jsonl,
    fetch,
    iso,
    now_utc,
    parse_dt,
    read_json,
    save_sample,
    write_json,
)
from parsers import parse_incidencias, parse_paneles  # noqa: E402

FEEDS = (("incidencias", parse_incidencias), ("paneles", parse_paneles))


def diff(prev_items, items, ts, bootstrap):
    prev = {i["id"]: i for i in prev_items}
    cur = {i["id"]: i for i in items}
    events = []
    for rid, item in cur.items():
        if rid not in prev:
            ev = {"t": ts, "ev": "open", **item}
            if bootstrap:
                ev["boot"] = True
            events.append(ev)
        elif prev[rid] != item:
            events.append({"t": ts, "ev": "change", **item})
    for rid in prev:
        if rid not in cur:
            events.append({"t": ts, "ev": "close", "id": rid})
    return events


def run(args):
    now = now_utc()
    ts = iso(now)
    day = ts[:10]
    month = ts[:7]
    any_ok = False
    for name, parser in FEEDS:
        run_row = {"t": ts, "feed": name}
        prev_path = os.path.join(args.prev, f"{name}.json")
        out_path = os.path.join(args.out, f"{name}.json")
        prev_doc = read_json(prev_path)
        t0 = time.time()
        try:
            data = fetch(SOURCES[name])
            run_row["bytes"] = len(data)
            run_row["ms"] = int((time.time() - t0) * 1000)
            save_sample(args.samples, name, data)
            items, meta = parser(data)
        except Exception as exc:  # noqa: BLE001
            run_row.update(ok=False, err=str(exc)[:300])
            append_jsonl(os.path.join(args.history, "runs", f"{month}.jsonl"), [run_row])
            if os.path.exists(prev_path):  # se conserva el último estado bueno
                os.makedirs(args.out, exist_ok=True)
                shutil.copyfile(prev_path, out_path)
            print(f"[{name}] ERROR: {exc}", file=sys.stderr)
            continue

        published = parse_dt(meta.get("published"))
        bootstrap = prev_doc is None
        events = diff(prev_doc["items"] if prev_doc else [], items, ts, bootstrap)
        doc = {
            "generated": ts,
            "published": meta.get("published"),
            "count": len(items),
            "meta": {"leaf_tags": meta.get("leaf_tags")},
            "items": items,
        }
        write_json(out_path, doc)
        append_jsonl(os.path.join(args.history, name, f"{day}.jsonl"), events)
        run_row.update(
            ok=True,
            published=meta.get("published"),
            lag_s=int((now - published).total_seconds()) if published else None,
            count=len(items),
            opens=sum(e["ev"] == "open" for e in events),
            changes=sum(e["ev"] == "change" for e in events),
            closes=sum(e["ev"] == "close" for e in events),
        )
        append_jsonl(os.path.join(args.history, "runs", f"{month}.jsonl"), [run_row])
        any_ok = True
        print(f"[{name}] {len(items)} elementos, {len(events)} eventos")
    return 0 if any_ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default="prev", help="carpeta con el estado anterior (rama latest)")
    ap.add_argument("--out", default="latest", help="carpeta de salida con el estado actual")
    ap.add_argument("--history", default="data/history")
    ap.add_argument("--samples", default="data/samples")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()
