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


TYPE_EXCLUDE = {"vehicleType", "locationType"}


def _veh(v):
    return None if v in (None, "anyVehicle") else v


def _endpoint(rec, name):
    """Punto inicial ('from') o final ('to') del tramo: coordenadas y PK."""
    el = next(iter_local(rec, name), None)
    out = {"pt": None, "pk": None}
    if el is None:
        return out
    pts = coords(el)
    if pts:
        out["pt"] = list(pts[0])
    pks = kilometre_points(el)
    if pks:
        out["pk"] = round(pks[0], 3)
    return out


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
                if name.endswith("Type")
                and not name.startswith("tpeg")
                and name not in TYPE_EXCLUDE
            )[:4]
            frm, to = _endpoint(rec, "from"), _endpoint(rec, "to")
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
                "road": first_text(rec, "roadName", "roadNumber"),
                "dir": first_text(rec, "tpegDirectionRoad", "directionRelative", "directionBound"),
                "lanes": first_text(rec, "laneUsage"),
                "veh": _veh(first_text(rec, "vehicleType")),
                "pk": [x for x in (frm["pk"], to["pk"]) if x is not None]
                or _round_pk(kilometre_points(rec)),
                "a": frm["pt"] or (list(pts[0]) if pts else None),
                "b": to["pt"] or (list(pts[-1]) if len(pts) > 1 else None),
                "geo": geo or None,
                "text": comment,
            }
            items.append({k: v for k, v in item.items() if v not in (None, [], {}, "")})
    meta = {"published": published, "leaf_tags": leaf_tag_counts(root)}
    return items, meta


def parse_paneles(data):
    """Estado en tiempo real de los paneles de mensaje variable (VmsPublication v3.7).

    Un item por controlador y vmsStatus con mensaje activo (texto y/o pictogramas).
    El id del controlador coincide con el id de data/static/paneles_loc.json.
    """
    root = ET.fromstring(data)
    published = first_text(root, "publicationTime")
    items = []
    for st in iter_local(root, "vmsControllerStatus"):
        ref = next(iter_local(st, "vmsControllerReference"), None)
        ctrl = ref.get("id") if ref is not None else None
        if not ctrl:
            continue
        for vs in children_local(st, "vmsStatus"):
            idx = vs.get("vmsIndex") or "1"
            texts, picts = [], []
            for name, text in leaf_items(vs):
                if name == "textLine":
                    line = " / ".join(p.strip() for p in text.splitlines() if p.strip())
                    if line:
                        texts.append(line)
                elif name == "customPictogramCode":
                    picts.append(text)
            if not texts and not picts:
                continue
            item = {
                "id": f"{ctrl}.{idx}",
                "ctrl": ctrl,
                "texts": texts,
                "picts": _unique(picts),
                "time": first_text(vs, "timeLastSet"),
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
            "road": first_text(el, "roadNumber", "roadName"),
            "dest": first_text(el, "roadDestination"),
            "pk": _round_pk(kilometre_points(el)),
            "urls": urls,
            "extra": extra,
        }
        items.append({k: v for k, v in item.items() if v not in (None, [], {}, "")})
    meta = {"published": published, "leaf_tags": leaf_tag_counts(root)}
    return items, meta
