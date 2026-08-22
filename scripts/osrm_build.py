"""Construye y levanta el router OSRM (perfil car) para Peru en Docker.

Uso:
  python scripts/osrm_build.py --build   # extract+partition+customize
  python scripts/osrm_build.py --serve   # osrm-routed --algorithm mld (puerto 5000)
  python scripts/osrm_build.py --all     # build + serve (procesos secuenciales)
Requiere: data/raw/osm/peru-latest.osm.pbf y Docker Desktop en ejecucion.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OSM_DIR = ROOT / "data" / "raw" / "osm"
PBF = OSM_DIR / "peru-latest.osm.pbf"
OSRM = OSM_DIR / "peru-latest.osrm"
PORT = 5000
IMAGE = "osrm/osrm-backend"


def _docker(args, name, run_opts=None):
    cmd = ["docker", "run", "--rm"] + (run_opts or []) + ["-v", f"{OSM_DIR}:/data", IMAGE] + args
    print(f"[{name}] {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        sys.exit(r.returncode)
    out = r.stdout.strip()
    if out:
        print(f"[{name}] {out[-1500:]}", flush=True)


def build():
    if not PBF.exists():
        sys.exit(f"No existe {PBF}. Ejecuta primero scripts/download_osm.py")
    if not OSRM.exists():
        _docker(["osrm-extract", "-p", "/opt/car.lua", "/data/peru-latest.osm.pbf"], "extract")
    _docker(["osrm-partition", "/data/peru-latest.osrm"], "partition")
    _docker(["osrm-customize", "/data/peru-latest.osrm"], "customize")
    print("OK grafo OSRM construido")


def serve():
    _docker(
        ["osrm-routed", "--algorithm", "mld", "--port", str(PORT), "/data/peru-latest.osrm"],
        "serve",
        run_opts=["-p", f"{PORT}:{PORT}"],
    )
    print("OK osrm-routed en :5000")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all or a.build:
        build()
    if a.all or a.serve:
        time.sleep(2)
        serve()
    if not (a.all or a.build or a.serve):
        ap.print_help()


if __name__ == "__main__":
    main()
