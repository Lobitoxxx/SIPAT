"""Extrae el enlace de descarga real de un recurso desde su pagina HTML."""
import re
import sys

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}


def find_file_links(resource_id: str):
    for url in (
        f"https://www.datosabiertos.gob.pe/dataset/XXXX/resource/{resource_id}",
        f"https://www.datosabiertos.gob.pe/dataset/XXXX/resource/{resource_id}/download",
    ):
        try:
            html = requests.get(url, headers=UA, timeout=60).text
        except Exception:
            continue
        links = set(re.findall(r'href="([^"]*\.(?:xls|xlsx|csv|zip|docx|json|geojson|shp))"', html, re.I))
        links |= set(re.findall(r'href="([^"]*sites/default/files/[^"]*)"', html, re.I))
        if links:
            print(f"PAGINA: {url}")
            for l in sorted(links):
                print("   ", l)


if __name__ == "__main__":
    find_file_links(sys.argv[1])
