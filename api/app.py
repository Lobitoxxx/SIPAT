"""API FastAPI del modulo 'Ruta segura'.

Endpoints:
  POST /ruta_segura         {origin, dest, salida?, radio_alertas_km?}
  POST /ruta_segura_completa  mismo + clima/avisos SENAMHI/emergencias COEN
  GET  /alertas             alertas SUTRAN actuales (cache TTL 15 min)
  GET  /avisos              avisos SENAMHI + emergencias COEN (cache)
  GET  /health              estado del servicio

Uso:
  uvicorn api.app:app --host 0.0.0.0 --port 8000
"""

import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ruta_segura import analizar, resumen_analisis  # noqa: E402
from alertas_sutran import get_alertas  # noqa: E402
from riesgo_red import get_index  # noqa: E402
import reportes_ciudadanos as rep_ciu  # noqa: E402

app = FastAPI(title="SIPAT Ruta Segura", version="2.2.0")

_arranque = time.time()


class RutaRequest(BaseModel):
    origin: str
    dest: str
    salida: str | None = None
    radio_alertas_km: float = 2.0
    include_geometry: bool = True


@app.get("/health")
def health():
    idx = get_index()
    return {
        "status": "ok",
        "uptime_s": int(time.time() - _arranque),
        "puntos_riesgo": len(idx.xy),
        "alertas_hist": len(idx.alertas_hist),
        "osrm": "http://localhost:5000",
    }


@app.get("/alertas")
def alertas(force: bool = False):
    return {"n": len(get_alertas(force=force)), "alertas": get_alertas(force=force)}


@app.get("/avisos")
def avisos(force: bool = False):
    try:
        from clima import avisos_senamhi, emergencias_coen
        senamhi = avisos_senamhi(force=force)
        coen = emergencias_coen(force=force)
        return {"avisos_senamhi": senamhi, "emergencias_coen": coen,
                "fecha": time.strftime("%Y-%m-%d %H:%M")}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ruta_segura")
def ruta_segura(req: RutaRequest):
    try:
        res = analizar(req.origin, req.dest,
                       radio_alertas_km=req.radio_alertas_km,
                       salida=req.salida)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))
    return resumen_analisis(res, include_geometry=req.include_geometry)


@app.post("/ruta_segura_completa")
def ruta_segura_completa(req: RutaRequest):
    try:
        res = analizar(req.origin, req.dest,
                       radio_alertas_km=req.radio_alertas_km,
                       salida=req.salida)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))
    resumen = resumen_analisis(res, include_geometry=req.include_geometry)
    r0 = resumen["rutas"][0]
    resumen["resumen_riesgo"] = {
        "riesgo_historico": {
            "score_km": r0["score_km_penalizado"],
            "nivel": _nivel(r0["score_km_penalizado"], 4.0, 8.0),
        },
        "riesgo_predictivo": {
            "siniestros_km": (r0.get("prediccion") or {}).get("pred_siniestros_km", 0),
            "nivel": _nivel((r0.get("prediccion") or {}).get("pred_siniestros_km", 0), 0.5, 1.2),
            "cobertura_pct": (r0.get("prediccion") or {}).get("cobertura_pct", 0),
        },
    }
    resumen["clima"] = {"pronostico": None, "avisos_senamhi": [], "emergencias_coen": []}
    if res["rutas"]:
        geo = res["rutas"][0]["geometry"]
        try:
            from clima import (avisos_senamhi, avisos_en_ruta, pronostico_openmeteo,
                               emergencias_coen, emergencias_en_ruta)
            resumen["clima"]["pronostico"] = pronostico_openmeteo(geo)
            resumen["clima"]["avisos_senamhi"] = avisos_en_ruta(avisos_senamhi(), geo)
            resumen["clima"]["emergencias_coen"] = emergencias_en_ruta(emergencias_coen(), geo)
        except Exception:  # noqa: BLE001
            pass
    return resumen


class ReporteRequest(BaseModel):
    tipo: str
    descripcion: str
    lat: float
    lon: float
    severidad: str = "Moderado"
    autor: str = ""
    ref: str = ""


@app.get("/reportes")
def reportes_list(dias: int = 30):
    reps = rep_ciu.listar_reportes(dias=dias) or []
    return {"n": len(reps), "reportes": reps}


@app.post("/reportes")
def reportes_add(req: ReporteRequest):
    ok, msg, rep = rep_ciu.agregar_reporte(
        req.tipo, req.descripcion, req.lat, req.lon,
        autor=req.autor, severidad=req.severidad, ref=req.ref)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "mensaje": msg, "reporte": rep}


def _nivel(v, lo, hi):
    if v < lo:
        return "Bajo"
    if v <= hi:
        return "Medio"
    return "Alto"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
