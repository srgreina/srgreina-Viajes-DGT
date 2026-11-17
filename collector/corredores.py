"""Alertas de corredor: avisa al móvil (ntfy.sh) de lo grave que haya en tus rutas habituales poco antes de salir.

  CORREDORES='{"v":1,"corredores":[...]}' NTFY_TOPIC=... python collector/corredores.py --latest latest --prev prev

- Los corredores se exportan desde el planificador ("Copiar para avisos") y se guardan en el secreto de repo
  CORREDORES (el repo es público: el recorrido no debe estar en ningún fichero). NTFY_TOPIC es el tema secreto de ntfy.
- Sin cualquiera de los dos secretos termina sin error y sin hacer nada.
- Formato de un corredor: {"n": nombre, "d": [1..7 (lunes=1)], "h": "07:30" (hora local de Madrid), "l": [[lat, lon], ...],
  "dur": segundos, "dist": metros}.
- Se evalúa si la salida habitual cae entre 15 min antes y 90 min después de ahora. Se avisa de: incidencias graves
  (corte, accidente...) a menos de 150 m de la ruta, avisos AEMET naranja/rojo vigentes a la hora de paso y tiempo
  adverso (lluvia fuerte, rachas, hielo, niebla, tormenta). Solo se avisa si el conjunto cambia respecto al último aviso
  (estado en corredores_estado.json con claves hash; no contiene nombres ni coordenadas).
"""
import argparse
import hashlib
import json
import math
import os
import sys
import urllib.request
from datetime import timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA, iso, now_utc, parse_dt, read_json, write_json  # noqa: E402

try:
    from zoneinfo import ZoneInfo

    MADRID = ZoneInfo("Europe/Madrid")
except Exception:  # noqa: BLE001 - sin base de zonas horarias se avisa al evaluar
    MADRID = None

R_EARTH = 6371008.8
BUFFER_M = 150
WINDOW_BEFORE_MIN = 15
WINDOW_AFTER_MIN = 90
HIGH_TYPES = {"roadClosed", "carriagewayClosures", "accident", "vehicleOnFire", "rockfalls", "avalanches", "flooding"}
TYPE_ES = {
    "roadClosed": "Carretera cortada", "carriagewayClosures": "Cierre de calzada", "accident": "Accidente",
    "vehicleOnFire": "Vehículo en llamas", "rockfalls": "Desprendimientos", "avalanches": "Avalancha", "flooding": "Inundación",
}
ALERT_LEVELS = {"naranja", "rojo"}


# ---------- geometría ----------

def make_route(latlon, dur, dist):
    """latlon: [[lat, lon], ...]. Tiempos y distancias proporcionales (sin tráfico), como el planificador sin anotaciones."""
    lat0 = sum(p[0] for p in latlon) / len(latlon)
    c = math.cos(math.radians(lat0))
    pts = [(R_EARTH * math.radians(lo) * c, R_EARTH * math.radians(la)) for la, lo in latlon]
    seg = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    total = sum(seg) or 1.0
    cum_d, cum_t = [0.0], [0.0]
    for s in seg:
        cum_d.append(cum_d[-1] + (s / total) * dist)
        cum_t.append(cum_t[-1] + (s / total) * dur)
    return {"pts": pts, "ll": latlon, "cum_d": cum_d, "cum_t": cum_t, "c": c, "total_d": cum_d[-1], "total_t": cum_t[-1]}


def project(route, lat, lon):
    return R_EARTH * math.radians(lon) * route["c"], R_EARTH * math.radians(lat)


def nearest(route, lat, lon, buffer=BUFFER_M):
    """Punto más cercano de la ruta dentro del buffer: (dist, s, t) o None."""
    x, y = project(route, lat, lon)
    best = None
    pts = route["pts"]
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        if x < min(x1, x2) - buffer or x > max(x1, x2) + buffer or y < min(y1, y2) - buffer or y > max(y1, y2) + buffer:
            continue
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        u = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / l2)) if l2 else 0.0
        d = math.hypot(x - (x1 + u * dx), y - (y1 + u * dy))
        if d <= buffer and (best is None or d < best[0]):
            best = (d, i, u)
    if best is None:
        return None
    d, i, u = best
    cd, ct = route["cum_d"], route["cum_t"]
    return d, cd[i] + u * (cd[i + 1] - cd[i]), ct[i] + u * (ct[i + 1] - ct[i])


def nearest_line(route, a, b, step=120):
    x1, y1 = project(route, *a)
    x2, y2 = project(route, *b)
    k = min(400, max(1, math.ceil(math.hypot(x2 - x1, y2 - y1) / step)))
    best = None
    for j in range(k + 1):
        f = j / k
        h = nearest(route, a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        if h and (best is None or h[1] < best[1]):
            best = h
    return best


def sample_points(route, step=25000, max_pts=40):
    total = route["total_d"]

    def at(s):
        cd = route["cum_d"]
        lo, hi = 0, len(cd) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cd[mid] <= s:
                lo = mid
            else:
                hi = mid
        span = cd[hi] - cd[lo]
        u = min(1.0, max(0.0, (s - cd[lo]) / span)) if span > 0 else 0.0
        a, b = route["ll"][lo], route["ll"][hi]
        t = route["cum_t"][lo] + u * (route["cum_t"][hi] - route["cum_t"][lo])
        return {"s": s, "t": t, "lat": a[0] + (b[0] - a[0]) * u, "lon": a[1] + (b[1] - a[1]) * u}

    if not total > 0:
        return [at(0)]
    st = max(step, total / max_pts)
    out, s = [], 0.0
    while s < total:
        out.append(at(s))
        s += st
    if len(out) > 1 and total - out[-1]["s"] < st / 3:
        out.pop()
    out.append(at(total))
    return out


def point_in_ring(lat, lon, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


# ---------- evaluación ----------

def weather_alerts(w):
    a = []
    if not w:
        return a
    if w.get("code") is not None and w["code"] >= 95:
        a.append(("storm", "Tormenta"))
    if w.get("rain") is not None and w["rain"] >= 5:
        a.append(("rain", f"Lluvia fuerte ({w['rain']:.1f} mm/h)".replace(".", ",")))
    if w.get("gust") is not None and w["gust"] >= 70:
        a.append(("wind", f"Rachas de {round(w['gust'])} km/h"))
    if (w.get("snow") or 0) > 0 or (w.get("temp") is not None and w["temp"] <= 3 and (w.get("rain") or 0) > 0):
        a.append(("ice", "Riesgo de hielo o nieve"))
    if w.get("vis") is not None and w["vis"] < 1000:
        a.append(("vis", "Visibilidad menor de 1 km"))
    return a


def weather_at(resp, when_ts):
    h = (resp or {}).get("hourly")
    if not h or not h.get("time"):
        return None
    times = h["time"]
    i = min(range(len(times)), key=lambda k: abs(times[k] - when_ts))
    if abs(times[i] - when_ts) > 5400:
        return None

    def g(k):
        v = (h.get(k) or [None] * len(times))[i]
        return v

    return {"temp": g("temperature_2m"), "rain": g("precipitation"), "snow": g("snowfall"), "gust": g("wind_gusts_10m"),
            "vis": g("visibility"), "code": g("weather_code")}


def fetch_weather(points):
    q = lambda k: ",".join(f"{p[k]:.3f}" for p in points)  # noqa: E731
    url = ("https://api.open-meteo.com/v1/forecast?latitude=" + q("lat") + "&longitude=" + q("lon")
           + "&hourly=temperature_2m,precipitation,snowfall,wind_gusts_10m,visibility,weather_code"
           + "&timeformat=unixtime&timezone=GMT&forecast_days=3")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data if isinstance(data, list) else [data]


def evaluate(corridor, dep, inc_doc, avisos_doc, weather_fn=fetch_weather):
    """Alertas del corredor saliendo en `dep` (datetime con zona). Devuelve [{key, text, km, eta}] por km."""
    route = make_route(corridor["l"], corridor["dur"], corridor["dist"])
    alerts = []

    def eta(t):
        return (dep + timedelta(seconds=t)).astimezone(MADRID or timezone.utc).strftime("%H:%M")

    for it in (inc_doc or {}).get("items", []):
        types = set(it.get("types") or [])
        bad = types & HIGH_TYPES
        if not bad or not it.get("a"):
            continue
        h = nearest_line(route, it["a"], it["b"]) if it.get("b") else nearest(route, it["a"][0], it["a"][1])
        if not h:
            continue
        name = TYPE_ES[sorted(bad)[0]]
        where = f" en {it['road']}" if it.get("road") else ""
        alerts.append({"key": f"inc:{it.get('id')}", "text": f"{name}{where} (km {h[1] / 1000:.0f}, hacia las {eta(h[2])})",
                       "km": h[1], "eta": eta(h[2])})

    pts_av = sample_points(route, 1500, 400)
    for av in (avisos_doc or {}).get("items", []):
        if av.get("lvl") not in ALERT_LEVELS:
            continue
        f, t = parse_dt(av.get("from")), parse_dt(av.get("to"))
        if not f or not t:
            continue
        inside = [p for p in pts_av
                  if f <= dep + timedelta(seconds=p["t"]) <= t
                  and any(point_in_ring(p["lat"], p["lon"], r) for r in av.get("poly", []))]
        if inside:
            alerts.append({"key": f"avi:{av.get('id')}", "text": f"Aviso {av['lvl']}: {(av.get('ph') or av.get('ev') or '').lower()} en {av.get('area')} (km {inside[0]['s'] / 1000:.0f})",
                           "km": inside[0]["s"], "eta": eta(inside[0]["t"])})

    pts_wx = sample_points(route)
    try:
        resp = weather_fn(pts_wx)
    except Exception as exc:  # noqa: BLE001 - el tiempo es opcional
        print(f"corredores: sin tiempo ({str(exc)[:120]})", file=sys.stderr)
        resp = []
    seen = set()
    for p, r in zip(pts_wx, resp):
        for key, text in weather_alerts(weather_at(r, (dep + timedelta(seconds=p["t"])).timestamp())):
            if key in seen:
                continue
            seen.add(key)
            alerts.append({"key": f"wx:{key}", "text": f"{text} hacia las {eta(p['t'])} (km {p['s'] / 1000:.0f})", "km": p["s"], "eta": eta(p["t"])})
    return sorted(alerts, key=lambda a: a["km"])


# ---------- ventana, estado y envío ----------

def departure_due(corridor, now):
    """Salida habitual (datetime UTC) si cae entre 15 min antes y 90 min después de `now`; si no, None."""
    if MADRID is None:
        return None
    local = now.astimezone(MADRID)
    try:
        hh, mm = (int(x) for x in corridor["h"].split(":"))
    except (KeyError, ValueError):
        return None
    for day_off in (0, 1):  # hoy y mañana (por si la salida es justo tras medianoche)
        d = (local + timedelta(days=day_off)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if d.isoweekday() not in corridor.get("d", []):
            continue
        delta = (d - local).total_seconds() / 60
        if -WINDOW_BEFORE_MIN <= delta <= WINDOW_AFTER_MIN:
            return d.astimezone(timezone.utc)
    return None


def signature(corridor, dep, alerts):
    base = f"{corridor.get('n')}|{dep.astimezone(MADRID or timezone.utc).strftime('%Y-%m-%d %H:%M')}|{'|'.join(sorted(a['key'] for a in alerts))}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def message(corridor, dep, alerts, max_lines=6):
    hora = dep.astimezone(MADRID or timezone.utc).strftime("%H:%M")
    title = f"{corridor.get('n', 'Corredor')} · salida {hora}: {len(alerts)} aviso{'s' if len(alerts) != 1 else ''}"
    lines = [f"• {a['text']}" for a in alerts[:max_lines]]
    if len(alerts) > max_lines:
        lines.append(f"…y {len(alerts) - max_lines} más")
    return title, "\n".join(lines)


def send_ntfy(topic, title, body, priority=4, post=None):
    payload = json.dumps({"topic": topic, "title": title, "message": body, "priority": priority, "tags": ["warning", "car"]}).encode("utf-8")
    req = urllib.request.Request("https://ntfy.sh/", data=payload, headers={"User-Agent": UA, "Content-Type": "application/json"}, method="POST")
    with (post or urllib.request.urlopen)(req, timeout=20) as r:
        return getattr(r, "status", 200)


def run(corridors, now, inc_doc, avisos_doc, state, topic, weather_fn=fetch_weather, sender=send_ntfy):
    """Devuelve (nuevo_estado, enviados). state: {'sent': {firma: iso}} (se purga lo de más de 3 días)."""
    sent_state = {k: v for k, v in (state or {}).get("sent", {}).items()
                  if (parse_dt(v) or now) > now - timedelta(days=3)}
    sent = []
    for c in corridors:
        try:
            dep = departure_due(c, now)
            if not dep:
                continue
            alerts = evaluate(c, dep, inc_doc, avisos_doc, weather_fn)
            if not alerts:
                continue
            sig = signature(c, dep, alerts)
            if sig in sent_state:
                continue
            title, body = message(c, dep, alerts)
            sender(topic, title, body)
            sent_state[sig] = iso(now)
            sent.append(title)
        except Exception as exc:  # noqa: BLE001 - un corredor malo no debe frenar a los demás ni revelar datos
            print(f"corredores: error en un corredor ({type(exc).__name__})", file=sys.stderr)
    return {"sent": sent_state}, sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default="latest")
    ap.add_argument("--prev", default="prev")
    args = ap.parse_args()
    raw, topic = os.environ.get("CORREDORES", "").strip(), os.environ.get("NTFY_TOPIC", "").strip()
    if not raw or not topic:
        print("corredores: sin CORREDORES o NTFY_TOPIC, se omite")
        return 0
    try:
        corridors = json.loads(raw).get("corredores", [])
    except ValueError:
        print("corredores: el secreto CORREDORES no es un JSON válido", file=sys.stderr)
        return 1
    if MADRID is None:
        print("corredores: no hay base de zonas horarias (zoneinfo)", file=sys.stderr)
        return 1
    state = read_json(os.path.join(args.prev, "corredores_estado.json")) or {}
    state, sent = run(corridors, now_utc(), read_json(os.path.join(args.latest, "incidencias.json")),
                      read_json(os.path.join(args.latest, "avisos.json")), state, topic)
    os.makedirs(args.latest, exist_ok=True)
    write_json(os.path.join(args.latest, "corredores_estado.json"), state)
    print(f"corredores: {len(corridors)} corredores, {len(sent)} avisos enviados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
