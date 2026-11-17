"""Limpieza semanal del histórico (data/history): borra lo que ya no hace falta.

  python collector/limpieza.py --history data/history [--keep-days 8]

- incidencias/ y paneles/ (un fichero por día UTC): se borran los de más de KEEP_DAYS días. Con 8 queda siempre la
  semana completa que lee el resumen semanal.
- incidencias/: además solo se borra un día si riesgo.py ya lo ha procesado (día <= `through` de riesgo_estado.json);
  si el estado no existe o va por detrás, se conserva.
- runs/ (un fichero por mes): se conservan el mes actual y el anterior (calidad.py solo lee las últimas 24 h).
- No toca riesgo_estado.json ni nada fuera de data/history. Git conserva el pasado: esto frena el crecimiento, no lo reduce.
"""
import argparse
import glob
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import now_utc, read_json  # noqa: E402

KEEP_DAYS = 8


def month_before(d):
    first = d.replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y-%m")


def plan(history, now, keep_days=KEEP_DAYS):
    """Devuelve la lista de ficheros a borrar."""
    limit = (now - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    through = (read_json(os.path.join(history, "riesgo_estado.json")) or {}).get("through")
    out = []
    for sub in ("incidencias", "paneles"):
        for f in glob.glob(os.path.join(history, sub, "*.jsonl")):
            day = os.path.basename(f)[:-6]
            if len(day) != 10 or day >= limit:
                continue
            if sub == "incidencias" and not (through and day <= through):
                continue  # riesgo.py aún no lo ha procesado
            out.append(f)
    keep_months = {now.strftime("%Y-%m"), month_before(now)}
    for f in glob.glob(os.path.join(history, "runs", "*.jsonl")):
        month = os.path.basename(f)[:-6]
        if len(month) == 7 and month not in keep_months:
            out.append(f)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="data/history")
    ap.add_argument("--keep-days", type=int, default=KEEP_DAYS)
    args = ap.parse_args()
    files = plan(args.history, now_utc(), args.keep_days)
    for f in files:
        os.remove(f)
    print(f"limpieza: {len(files)} ficheros borrados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
