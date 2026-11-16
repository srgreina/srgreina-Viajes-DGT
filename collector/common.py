"""Utilidades comunes: descarga, helpers XML (sin depender del prefijo de namespace) y E/S JSON."""
import gzip
import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone

UA = "Viajes-DGT/0.1 (+https://github.com/srgreina/srgreina-viajes-dgt)"

SOURCES = {
    "incidencias": "https://nap.dgt.es/datex2/v3/dgt/SituationPublication/datex2_v37.xml",
    "paneles": "https://nap.dgt.es/datex2/v3/dgt/VmsPublication/datex2_v37.xml",
    "paneles_loc": "https://nap.dgt.es/datex2/v3/dgt/DevicePublication/vms_datex2_v37.xml",
    "camaras": "https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v37.xml",
    "radares": "https://nap.dgt.es/datex2/dgt/PredefinedLocationsPublication/radares/content.xml",
}


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_dt(text):
    """Parsea fechas ISO 8601 del feed (con o sin offset). Devuelve None si no puede."""
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch(url, retries=3, timeout=90):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                return data
        except Exception as exc:  # noqa: BLE001 - se reintenta con cualquier fallo de red
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"fallo al descargar {url}: {last}")


# ---------- helpers XML ----------

def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def attr(el, name):
    """Atributo por nombre local (p. ej. 'type' para xsi:type)."""
    for key, value in el.attrib.items():
        if local(key) == name:
            return value
    return None


def iter_local(el, name):
    for d in el.iter():
        if local(d.tag) == name:
            yield d


def children_local(el, name):
    return [c for c in el if local(c.tag) == name]


def is_leaf_with_text(el):
    return len(el) == 0 and el.text is not None and el.text.strip() != ""


def first_text(el, *names):
    wanted = set(names)
    for d in el.iter():
        if local(d.tag) in wanted and d.text and d.text.strip():
            return d.text.strip()
    return None


def leaf_items(el):
    """Pares (nombre_local, texto) de todas las hojas con texto bajo el."""
    return [(local(d.tag), d.text.strip()) for d in el.iter() if is_leaf_with_text(d)]


def coords(el):
    """Lista de (lat, lon) de los pointCoordinates bajo el."""
    out = []
    for pc in iter_local(el, "pointCoordinates"):
        lat = first_text(pc, "latitude")
        lon = first_text(pc, "longitude")
        try:
            out.append((round(float(lat), 6), round(float(lon), 6)))
        except (TypeError, ValueError):
            continue
    return out


def kilometre_points(el):
    pks = []
    for name, text in leaf_items(el):
        low = name.lower()
        if "kilomet" in low:
            try:
                pks.append(float(text.replace(",", ".")))
            except ValueError:
                continue
    return pks


def smallest_matching(root, predicate):
    """Elementos con atributo id que cumplen predicate y no contienen otro que también cumpla."""
    parent = {c: p for p in root.iter() for c in p}
    candidates = [e for e in root.iter() if e.get("id") and predicate(e)]
    cand_set = set(candidates)
    has_inner = set()
    for c in candidates:
        p = parent.get(c)
        while p is not None:
            if p in cand_set:
                has_inner.add(p)
            p = parent.get(p)
    return [c for c in candidates if c not in has_inner]


def leaf_tag_counts(root, top=80):
    cnt = Counter(local(d.tag) for d in root.iter() if is_leaf_with_text(d))
    return dict(cnt.most_common(top))


# ---------- E/S ----------

def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def append_jsonl(path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def save_sample(samples_dir, name, data, limit=40_000):
    """Guarda una sola vez el principio del XML crudo, para ajustar los parsers."""
    if not samples_dir:
        return
    path = os.path.join(samples_dir, f"{name}.head.xml")
    if os.path.exists(path):
        return
    os.makedirs(samples_dir, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data[:limit])
