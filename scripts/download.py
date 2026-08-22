"""Descarga un archivo con headers de navegador y guarda en el destino indicado."""
import sys
import time
from pathlib import Path

import requests

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}


def download(url: str, dest: str, timeout: int = 180) -> None:
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 0:
        print(f"EXISTE: {dest_path} ({dest_path.stat().st_size} bytes)")
        return
    for attempt in range(3):
        try:
            with requests.get(url, headers=UA, timeout=timeout, stream=True) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
            size = dest_path.stat().st_size
            print(f"OK: {dest_path.name} -> {size:,} bytes")
            return
        except Exception as e:
            print(f"INTENTO {attempt + 1} fallo para {url}: {e}")
            time.sleep(3)
    raise SystemExit(f"FALLO descarga: {url}")


if __name__ == "__main__":
    url, dest = sys.argv[1], sys.argv[2]
    download(url, dest)
