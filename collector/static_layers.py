"""Capas de baja frecuencia: radares fijos, cámaras y localizaciones de paneles.

Uso:
  python collector/static_layers.py --out data/static --samples data/samples

Solo reescribe un fichero si su contenido ha cambiado (sin contar la marca de tiempo).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from common import SOURCES, fetch, iso, now_utc, read_json, save_sample, write_json  # noqa: E402
from parsers import parse_located  # noqa: E402

LAYERS = ("radares", "camaras", "paneles_loc")


def run(args):
    ts = iso(now_utc())
    ok = 0
    for name in LAYERS:
        path = os.path.join(args.out, f"{name}.json")
        try:
            data = fetch(SOURCES[name])
            save_sample(args.samples, name, data)
            items, meta = parse_located(data)
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] ERROR: {exc}", file=sys.stderr)
            continue
        old = read_json(path)
        if old and old.get("items") == items:
            print(f"[{name}] sin cambios ({len(items)})")
            ok += 1
            continue
        write_json(
            path,
            {
                "generated": ts,
                "published": meta.get("published"),
                "count": len(items),
                "meta": {"leaf_tags": meta.get("leaf_tags")},
                "items": items,
            },
        )
        print(f"[{name}] actualizado: {len(items)} elementos")
        ok += 1
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/static")
    ap.add_argument("--samples", default="data/samples")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()
