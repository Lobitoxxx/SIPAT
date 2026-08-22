"""Extrae los enlaces de archivos de descarga de una pagina de dataset."""
import re
import sys

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
EXT = re.compile(r"\.(csv|xls|xlsx|zip|geojson|json|shp|kml|docx|pdf|arcgis)(\?|$)", re.I)


def scrape(url: str) -> None:
    html = requests.get(url, headers=UA, timeout=90).text
    files = sorted(
        set(re.findall(r'href="([^"]*sites/default/files/[^"]+)"', html))
    )
    print(f"URL: {url}")
    for f in files:
        if EXT.search(f):
            print("   ", f)


if __name__ == "__main__":
    scrape(sys.argv[1])
