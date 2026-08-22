#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genera exportaciones (JSON/CSV) y reportes HTML para rutas de referencia.
"""
import sys
import os
import json
import pandas as pd
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from scripts.ruta_segura import analizar, resumen_analisis
from scripts.reporte_ruta import reporte_desde_resumen

OUT_DIR = ROOT / "data" / "processed" / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REFERENCE_ROUTES = [
    ("Lima_Huancayo", "Lima", "Huancayo", "2026-08-15 06:00"),
    ("Trujillo_Chiclayo", "Trujillo", "Chiclayo", "2026-08-15 06:00"),
]

def export_route(slug, origin, dest, salida):
    print(f"[EXPORT] {slug}: {origin} -> {dest} @ {salida}")
    res = analizar(origin, dest, salida=salida)
    resumen = resumen_analisis(res)
    
    # JSON export
    json_path = OUT_DIR / f"ruta_export_{slug}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(f"  JSON: {json_path} ({json_path.stat().st_size//1024} KB)")
    
    # CSV export - flatten key info
    rows = []
    for i, r in enumerate(resumen.get("rutas", [])):
        row = {
            "slug": slug,
            "ranking": r.get("ranking", ""),
            "km": r.get("km"),
            "minutos": r.get("minutos"),
            "score_km_penalizado": r.get("score_km_penalizado"),
            "n_accidentes_hist": len(r.get("accidentes_hist", [])),
            "n_alertas_vivas": len(r.get("alertas_vivas", [])),
            "perfil_promedio": sum(s.get("score_km", 0) for s in r.get("perfil", [])) / max(len(r.get("perfil", [])), 1) if r.get("perfil") else None,
        }
        if "prediccion" in r:
            row["pred_siniestros_km"] = r["prediccion"].get("pred_siniestros_km")
            row["pred_cobertura_pct"] = r["prediccion"].get("cobertura_pct")
        rows.append(row)
    csv_path = OUT_DIR / f"ruta_export_{slug}.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  CSV: {csv_path} ({csv_path.stat().st_size//1024} KB)")
    
    # HTML report
    html_path = OUT_DIR / f"reporte_{slug}.html"
    reporte_desde_resumen(resumen, str(html_path))
    print(f"  HTML: {html_path} ({html_path.stat().st_size//1024} KB)")

def main():
    for slug, origin, dest, salida in REFERENCE_ROUTES:
        try:
            export_route(slug, origin, dest, salida)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    print("\n[OK] Exportaciones y reportes generados")

if __name__ == "__main__":
    main()