"""Geocodificación lineal por km sobre la Red Vial Nacional (shapefile dic16).

locate(route, km) -> Point | None  : interpola la coordenada del km en la ruta.
snap_distance(point, route) -> float : distancia mínima de un punto a la ruta (validación).
"""
import math

import shapefile
from shapely.geometry import LineString, Point, MultiLineString

SH = r"data/raw/mtc_datos_espaciales/rvn_dic16/red_vial_nacional_dic16.shp"

R = 6371.0  # km


def _haversine(p1, p2):
    lon1, lat1 = math.radians(p1[0]), math.radians(p1[1])
    lon2, lat2 = math.radians(p2[0]), math.radians(p2[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _interp_geodesic(line: LineString, km_offset: float):
    """Punto a km_offset (km) a lo largo de la linea (distancias geodesicas)."""
    pts = list(line.coords)
    cum = 0.0
    prev = pts[0]
    for cur in pts[1:]:
        seg_len = _haversine(prev, cur)
        if km_offset <= cum + seg_len:
            frac = (km_offset - cum) / seg_len if seg_len else 0.0
            x = prev[0] + frac * (cur[0] - prev[0])
            y = prev[1] + frac * (cur[1] - prev[1])
            return Point(x, y)
        cum += seg_len
        prev = cur
    return Point(pts[-1])

# cache global
_SEGMENTS = None
_ROUTES = None


def _load():
    global _SEGMENTS, _ROUTES
    if _SEGMENTS is not None:
        return
    sf = shapefile.Reader(SH, encoding="iso-8859-1")
    fields = [f[0] for f in sf.fields[1:]]
    segments = []
    for rec, shape in zip(sf.iterRecords(), sf.iterShapes()):
        attrs = dict(zip(fields, list(rec)))
        if shape.shapeType != 3 or len(shape.points) < 2:
            continue
        geom = LineString(shape.points)
        segments.append({
            "route": attrs["cCodRutaDi"],
            "km0": float(attrs["dkmInicio"]),
            "km1": float(attrs["dkmFinal"]),
            "geom": geom,
            "dpto": attrs.get("cDepartame"),
            "region": attrs.get("cRegion"),
            "clasifica": attrs.get("cClasifica"),
            "topografia": attrs.get("cTopografi"),
            "carriles": attrs.get("dNroCarril"),
            "vel_proy": attrs.get("dVelProTra"),
            "superficie": attrs.get("cEstadoDic"),
        })
    _SEGMENTS = segments
    routes = {}
    for seg in segments:
        routes.setdefault(seg["route"], []).append(seg)
    _ROUTES = routes


def routes() -> set:
    _load()
    return set(_ROUTES.keys())


def route_geometry(route: str):
    """Linestring unida de toda la ruta (para distancia punto->ruta)."""
    _load()
    segs = _ROUTES.get(route)
    if not segs:
        return None
    lines = [s["geom"] for s in sorted(segs, key=lambda s: s["km0"])]
    if len(lines) == 1:
        return lines[0]
    return MultiLineString(lines)


def locate(route: str, km: float, tol_km: float = 5.0):
    """Interpola el punto de la ruta en el km dado. None si la ruta no existe.

    Si km cae fuera de los tramos (con tolerancia tol_km), se clampa al extremo.
    """
    _load()
    segs = _ROUTES.get(route)
    if not segs:
        return None
    best = None
    for s in segs:
        if s["km0"] <= km <= s["km1"]:
            best = s
            break
    if best is None:
        # buscar el segmento con el extremo más cercano
        best = min(segs, key=lambda s: min(abs(km - s["km0"]), abs(km - s["km1"])))
        if km < best["km0"] and abs(km - best["km0"]) > tol_km:
            return None
        if km > best["km1"] and abs(km - best["km1"]) > tol_km:
            return None
    km_offset = max(0.0, km - best["km0"])
    return _interp_geodesic(best["geom"], km_offset)


def snap_distance(point, route: str):
    """Distancia en grados del punto a la geometría de la ruta (validación)."""
    _load()
    g = route_geometry(route)
    if g is None:
        return None
    return point.distance(g)


if __name__ == "__main__":
    p = locate("PE-1S", 276.1)
    print("PE-1S km276.1 (peaje Ica):", p)
    print("rutas:", len(routes()))
