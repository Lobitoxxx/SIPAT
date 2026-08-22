"""Descarga el extracto OSM de Peru desde Geofabrik (peru-latest.osm.pbf).

Uso: python scripts/download_osm.py
Salida: data/raw/osm/peru-latest.osm.pbf (~242 MB)
"""

import sys
import urllib.request
from pathlib import Path

URL = "https://download.geofabrik.de/south-america/peru-latest.osm.pbf"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "osm" / "peru-latest.osm.pbf"
MIN_SIZE = 200 * 1024 * 1024


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and OUT.stat().st_size > MIN_SIZE:
        print(f"OK ya existe {OUT} ({OUT.stat().st_size/1024/1024:.0f} MB)")
        return
    print(f"Descargando {URL}")
    req = urllib.request.Request(URL, headers={"User-Agent": "SIPAT-ruta-segura/1.0"})
    tmp = OUT.with_suffix(".part")
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if done % (64 << 20) < (1 << 20):
                print(f"  {done/1024/1024:.0f} MB / {total/1024/1024:.0f} MB", flush=True)
    tmp.replace(OUT)
    print(f"OK {OUT} ({OUT.stat().st_size/1024/1024:.0f} MB)")


if __name__ == "__main__":
    sys.exit(main())
