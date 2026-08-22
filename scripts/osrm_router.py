"""Cliente HTTP para el router OSRM local (localhost:5000, perfil car).

Uso desde otros modulos:
  from osrm_router import OSRMClient
  c = OSRMClient()
  ruts = c.route([(lon1,lat1),(lon2,lat2)], alternatives=3)
"""

import urllib.parse
import urllib.request
import json

BASE = "http://localhost:5000"


class OSRMClient:
    def __init__(self, base=BASE, timeout=120):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def _get(self, service, args, params):
        coords = ";".join(f"{lon},{lat}" for lon, lat in args)
        q = urllib.parse.urlencode(params)
        url = f"{self.base}/{service}/v1/driving/{coords}?{q}"
        with urllib.request.urlopen(url, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def route(self, coords, alternatives=3, steps=False):
        """coords: [(lon,lat), ...]; devuelve lista de dicts de rutas."""
        params = {
            "alternatives": str(alternatives),
            "overview": "full",
            "geometries": "geojson",
            "steps": "true" if steps else "false",
        }
        data = self._get("route", coords, params)
        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM route error: {data.get('code')} {data.get('message')}")
        return [
            {
                "distance_m": r["distance"],
                "duration_s": r["duration"],
                "geometry": r["geometry"],
                "legs": r.get("legs", []),
            }
            for r in data["routes"]
        ]

    def nearest(self, lon, lat):
        data = self._get("nearest", [(lon, lat)], {"number": 1})
        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM nearest error: {data.get('code')}")
        wp = data["waypoints"][0]
        return {"lon": wp["location"][0], "lat": wp["location"][1], "distance_m": wp["distance"]}


if __name__ == "__main__":
    c = OSRMClient()
    rutas = c.route([(-77.02824, -12.04637), (-75.20452, -12.06513)], alternatives=3)  # Lima->Huancayo
    for i, r in enumerate(rutas):
        print(f"ruta {i}: {r['distance_m']/1000:.1f} km, {r['duration_s']/60:.0f} min")
