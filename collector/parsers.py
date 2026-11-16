"""Parsers de los feeds DATEX II de la DGT.

Se localizan los elementos por nombre local (sin prefijo de namespace) para no depender
del prefijo ni de la versión exacta del perfil. El de incidencias está escrito según la
estructura publicada (situation > situationRecord). Los de paneles y capas estáticas son
genéricos y se afinan con las muestras que guarda el recolector en data/samples/.
"""
import re
import xml.etree.ElementTree as ET

from common import (
    attr,
    children_local,
    coords,
    first_text,
    is_leaf_with_text,
    iter_local,
    kilometre_points,
    leaf_items,
    leaf_tag_counts,
    local,
    smallest_matching,
)

GEO_RE = re.compile(r"(provinc|communit|comunidad|municip|town|^ine)", re.I)
TEXT_RE = re.compile(r"(text|message|pictogram|legend)", re.I)
NAME_TAGS = {"value", "name"}
EXTRA_RE = re.compile(r"(provinc|municip|orientation|direction|speed|limit|type|kind)", re.I)


def _unique(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _round_pk(pks):
    return [round(p, 3) for p in pks[:2]]


def parse_incidencias(data):
    """Devuelve (items, meta). Un item por situationRecord."""
    root = ET.fromstring(data)
    published = first_text(root, "publicationTime")
    items = []
    for sit in iter_local(root, "situation"):
        sid = sit.get("id")
        for n, rec in enumerate(children_local(sit, "situationRecord")):
            rid = rec.get("id") or (f"{sid}:{n}" if sid else None)
            if not rid:
                continue
            kind = (attr(rec, "type") or "").split(":")[-1]
            types = _unique(
                t
                for name, t in leaf_items(rec)
                if name.endswith("Type") and name != "locationType"
            )[:4]
            pts = coords(rec)
            geo = {}
            for name, text in leaf_items(rec):
                if GEO_RE.search(name) and name not in geo:
                    geo[name] = text
            comment = None
            for c in iter_local(rec, "comment"):
                comment = first_text(c, "value") or (c.text or "").strip() or None
                if comment:
                    break
            item = {
                "id": rid,
                "sit": sid,
                "ver": rec.get("version"),
                "kind": kind,
                "types": types,
                "status": first_text(rec, "validityStatus"),
                "created": first_text(rec, "situationRecordCreationTime"),
                "start": first_text(rec, "overallStartTime"),
                "end": first_text(rec, "overallEndTime"),
                "road": first_text(rec, "roadNumber"),
                "dir": first_text(rec, "directionRelative", "directionBound"),
                "pk": _round_pk(kilometre_points(rec)),
                "a": list(pts[0]) if pts else None,
                "b": list(pts[-1]) if len(pts) > 1 else None,
                "geo": geo or None,
                "text": comment,
            }
            items.append({k: v for k, v in item.items() if v not in (None, [], {}, "")})
    meta = {"published": published, "leaf_tags": leaf_tag_counts(root)}
    return items, meta


def parse_paneles(data):
    """Estado en tiempo real de los paneles de mensaje variable (parser genérico)."""
    root = ET.fromstring(data)
    published = first_text(root, "publicationTime")

    def has_message(el):
        return any(
            TEXT_RE.search(name) for name, _ in leaf_items(el)
        )

    items = []
    for el in smallest_matching(root, has_message):
        texts = _unique(
            t for name, t in leaf_items(el) if TEXT_RE.search(name)
        )
        pts = coords(el)
        item = {
            "id": el.get("id"),
            "kind": local(el.tag),
            "texts": texts[:6],
            "time": first_text(el, "timeLastSet", "vmsMessageTimeLastSet", "publicationTime"),
            "a": list(pts[0]) if pts else None,
        }
        items.append({k: v for k, v in item.items() if v not in (None, [], {}, "")})
    meta = {"published": published, "leaf_tags": leaf_tag_counts(root)}
    return items, meta


def parse_located(data):
    """Capas con posición (radares, cámaras, localizaciones de paneles). Genérico."""
    root = ET.fromstring(data)
    published = first_text(root, "publicationTime")

    def has_point(el):
        return any(True for _ in iter_local(el, "pointCoordinates"))

    items = []
    for el in smallest_matching(root, has_point):
        pts = coords(el)
        if not pts:
            continue
        lat, lon = pts[0]
        leaves = leaf_items(el)
        names = _unique(t for n, t in leaves if n in NAME_TAGS and not t.startswith("http"))[:3]
        urls = _unique(t for _, t in leaves if t.startswith("http"))[:3]
        extra = {}
        for n, t in leaves:
            if EXTRA_RE.search(n) and n not in extra and not t.startswith("http"):
                extra[n] = t
        item = {
            "id": el.get("id"),
            "lat": lat,
            "lon": lon,
            "names": names,
            "road": first_text(el, "roadNumber"),
            "pk": _round_pk(kilometre_points(el)),
            "urls": urls,
            "extra": extra,
        }
        items.append({k: v for k, v in item.items() if v not in (None, [], {}, "")})
    meta = {"published": published, "leaf_tags": leaf_tag_counts(root)}
    return items, meta
