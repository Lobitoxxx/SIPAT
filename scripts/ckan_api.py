"""Lista los recursos de un dataset del portal Datos Abiertos vía API CKAN."""
import json
import re
import sys

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
API = "https://www.datosabiertos.gob.pe/api/3/action/package_show"


def package(pkg_id: str) -> dict:
    r = requests.get(API, params={"id": pkg_id}, headers=UA, timeout=90)
    r.raise_for_status()
    data = r.json()
    res = data["result"]
    return res[0] if isinstance(res, list) else res


def resource_download_url(resource_id: str) -> str | None:
    """La URL directa puede dar 404; se extrae del HTML de la página del recurso."""
    page = (
        "https://www.datosabiertos.gob.pe/dataset/XXXX/resource/"
        + resource_id
    )
    return None  # placeholder


if __name__ == "__main__":
    pkg = package(sys.argv[1])
    print(f"TITULO: {pkg['title']}")
    print(f"Frecuencia: {pkg.get('frequency')}   Licencia: {pkg.get('license_id')}")
    print(f"Ultima modificacion: {pkg.get('metadata_modified')}")
    print("-" * 80)
    for i, res in enumerate(pkg["resources"]):
        print(f"[{i}] {res.get('format')} | {res.get('name')}")
        print(f"    url: {res.get('url')}")
        print(f"    id:  {res.get('id')}")
