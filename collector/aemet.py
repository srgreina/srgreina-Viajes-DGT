"""Avisos meteorológicos de AEMET (CAP) -> avisos.json.

  AEMET_API_KEY=... python collector/aemet.py --prev prev --out latest --samples data/samples

- Sin AEMET_API_KEY termina sin error y sin escribir nada (el front simplemente no ofrece la capa).
- Endpoint OpenData `avisos_cap/ultimoelaborado/area/esp`: devuelve JSON con la URL `datos` de un tar con un CAP por aviso.
- Solo se vuelve a descargar si el avisos.json anterior tiene más de REFRESH_S segundos; si no, se copia.
- Una descarga fallida conserva el último estado bueno (como en realtime.py).
"""
import argparse
import io
import json
import os
import re
import shutil
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA, fetch, iso, now_utc, parse_dt, read_json, write_json  # noqa: E402

ENDPOINT = "https://opendata.aemet.es/opendata/api/avisos_cap/ultimoelaborado/area/esp"
REFRESH_S = 25 * 60
LEVELS = ("amarillo", "naranja", "rojo")
SEVERITY_LEVEL = {"minor": "amarillo", "moderate": "amarillo", "severe": "naranja", "extreme": "rojo"}


def _l(tag):
    return tag.rsplit("}", 1)[-1]


def _kids(el, name):
    return [c for c in el if _l(c.tag) == name]


def _text(el, name):
    for c in _kids(el, name):
        if c.text and c.text.strip():
            return c.text.strip()
    return ""


def _params(el, container="parameter"):
    out = {}
    for p in _kids(el, container):
        k, v = _text(p, "valueName"), _text(p, "value")
        if k:
            out[k] = v
    return out


def parse_poly(text, nd=3):
    pts = []
    for pair in text.split():
        try:
            la, lo = pair.split(",")
            pts.append([round(float(la), nd), round(float(lo), nd)])
        except ValueError:
            continue
    return pts if len(pts) >= 3 else None


def level_of(info):
    nivel = _params(info).get("AEMET-Meteoalerta nivel", "").lower()
    if nivel in LEVELS:
        return nivel
    ev = _text(info, "event").lower()
    for lv in LEVELS:
        if lv in ev:
            return lv
    return SEVERITY_LEVEL.get(_text(info, "severity").lower())


def pick_info(alert):
    infos = _kids(alert, "info")
    for i in infos:
        if _text(i, "language").lower().startswith("es"):
            return i
    return infos[0] if infos else None


def parse_cap(xml_bytes, now):
    """Devuelve (identifier, referenced_ids, [items]) de un CAP; items vacío si no aplica."""
    root = ET.fromstring(xml_bytes)
    ident = _text(root, "identifier")
    refs = set()
    for tri in _text(root, "references").split():
        parts = tri.split(",")
        if len(parts) >= 2:
            refs.add(parts[1])
    if _text(root, "status").lower() != "actual" or _text(root, "msgType").lower() == "cancel":
        return ident, refs, []
    info = pick_info(root)
    if info is None:
        return ident, refs, []
    lvl = level_of(info)
    onset = parse_dt(_text(info, "onset")) or parse_dt(_text(info, "effective"))
    expires = parse_dt(_text(info, "expires"))
    if not lvl or not onset or not expires or expires <= now:
        return ident, refs, []
    code = _params(info, "eventCode").get("AEMET-Meteoalerta fenomeno", "")
    phen = code.split(";", 1)[1] if ";" in code else _text(info, "event")
    items = []
    for n, area in enumerate(_kids(info, "area")):
        polys = [p for p in (parse_poly(c.text or "") for c in _kids(area, "polygon")) if p]
        if not polys:
            continue
        zona = ""
        for g in _kids(area, "geocode"):
            if _text(g, "valueName") == "AEMET-Meteoalerta zona":
                zona = _text(g, "value")
        items.append({
            "id": f"{ident}#{n}",
            "zone": zona,
            "ev": _text(info, "event"),
            "ph": phen,
            "lvl": lvl,
            "area": _text(area, "areaDesc"),
            "desc": _text(info, "description"),
            "from": iso(onset),
            "to": iso(expires),
            "poly": polys,
        })
    return ident, refs, items


def parse_tar(data, now=None):
    now = now or now_utc()
    found, superseded = [], set()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.lower().endswith(".xml"):
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            try:
                ident, refs, items = parse_cap(f.read(), now)
            except ET.ParseError:
                continue
            superseded |= refs
            found.append((ident, items))
    items = []
    for ident, its in found:
        if ident in superseded:
            continue
        items.extend(its)
    items.sort(key=lambda i: (i["from"], i["zone"], i["ph"]))
    return items


def api_get_json(url, key):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "api_key": key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default="prev")
    ap.add_argument("--out", default="latest")
    ap.add_argument("--samples", default=None)
    args = ap.parse_args()

    key = os.environ.get("AEMET_API_KEY", "").strip()
    if not key:
        print("aemet: sin AEMET_API_KEY, se omite")
        return 0

    prev_path = os.path.join(args.prev, "avisos.json")
    out_path = os.path.join(args.out, "avisos.json")
    os.makedirs(args.out, exist_ok=True)
    prev = read_json(prev_path)
    now = now_utc()
    if prev and prev.get("generated"):
        g = parse_dt(prev["generated"])
        if g and (now - g).total_seconds() < REFRESH_S:
            shutil.copyfile(prev_path, out_path)
            print("aemet: reciente, se reutiliza el estado anterior")
            return 0
    try:
        meta = api_get_json(ENDPOINT, key)
        url = meta.get("datos")
        if not url:
            raise RuntimeError(f"respuesta sin 'datos': {str(meta)[:200]}")
        raw = fetch(url, timeout=60)
        if args.samples and not os.path.exists(os.path.join(args.samples, "aemet_cap.sample.xml")):
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
                for m in tf.getmembers():
                    if m.isfile() and m.name.lower().endswith(".xml"):
                        os.makedirs(args.samples, exist_ok=True)
                        with open(os.path.join(args.samples, "aemet_cap.sample.xml"), "wb") as fh:
                            fh.write(tf.extractfile(m).read()[:40000])
                        break
        items = parse_tar(raw, now)
    except Exception as exc:  # noqa: BLE001 - conserva el último estado bueno
        msg = re.sub(re.escape(key), "***", str(exc))
        print(f"aemet: error: {msg}")
        if os.path.exists(prev_path):
            shutil.copyfile(prev_path, out_path)
        return 0
    write_json(out_path, {"generated": iso(now), "count": len(items), "items": items})
    print(f"aemet: {len(items)} avisos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
