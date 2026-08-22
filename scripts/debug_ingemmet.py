"""Depura la consulta de features de INGEMMET (layer 0)."""
import json

import requests

UA = {"User-Agent": "Mozilla/5.0"}
B = "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_PELIGROS_GEOLOGICOS/MapServer/0/query"

params = {
    "where": "1=1",
    "outFields": "*",
    "returnGeometry": "true",
    "resultRecordCount": "2",
    "f": "json",
    "outSR": "4326",
}
r = requests.get(B, params=params, headers=UA, timeout=180)
print("STATUS", r.status_code)
txt = r.text
print("LEN", len(txt))
print("HEAD", txt[:800])
