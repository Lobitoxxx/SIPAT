"""Descarga las capas de INGEMMET por rangos de OBJECTID y las guarda como GeoJSON."""
import json
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_PELIGROS_GEOLOGICOS/MapServer"
OUTDIR = Path("data/raw/ingemmet")
OUTDIR.mkdir(parents=True, exist_ok=True)
REPORT = []


def layer_info(layer_id: int) -> dict:
    return requests.get(f"{BASE}/{layer_id}", params={"f": "json"}, headers=UA, timeout=120).json()


def download_layer(layer_id: int) -> None:
    info = layer_info(layer_id)
    name = info.get("name", f"layer_{layer_id}")
    fields = [f["name"] for f in info.get("fields", [])]

    features = []
    lo = 1
    while True:
        hi = lo + 1999
        r = requests.get(
            f"{BASE}/{layer_id}/query",
            params={
                "where": f"OBJECTID >= {lo} AND OBJECTID <= {hi}",
                "outFields": "*",
                "returnGeometry": "true",
                "f": "json",
                "outSR": "4326",
            },
            headers=UA,
            timeout=300,
        )
        r.raise_for_status()
        d = r.json()
        feats = d.get("features", [])
        if not feats:
            break
        features.extend(feats)
        lo = hi + 1
        print(f"   ... {len(features)} acumulados")

    safe = "".join(c for c in name if c.isalnum() or c == " ").strip().replace(" ", "_")
    out = OUTDIR / f"layer{layer_id}_{safe}.geojson"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "fields": fields, "features": features}, f, ensure_ascii=False)
    print(f"   -> {out.name} ({len(features):,} features, {out.stat().st_size:,} bytes)")
    REPORT.append((layer_id, name, len(features), fields))


if __name__ == "__main__":
    for lid in (0, 1, 2, 3):
        try:
            download_layer(lid)
        except Exception as e:
            print(f"[layer {lid}] ERROR: {e}")
    print("\n=== RESUMEN ===")
    for lid, name, n, fields in REPORT:
        print(f"layer{lid} | {name} | {n:,} | campos={','.join(fields)}")
