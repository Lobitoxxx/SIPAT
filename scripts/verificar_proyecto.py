#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verificador de aceptación del proyecto SIPAT.
Ejecuta todas las comprobaciones y devuelve matriz PASS/FAIL + código de salida.
"""
import sys
import os
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"timeout {timeout}s"
    except Exception as e:
        return False, "", str(e)

def check_port(port, host="localhost"):
    import socket
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False

def check_data_assets():
    checks = []
    assets = {
        "data/processed/tramos_red.csv": (True, "tramos red vial"),
        "data/processed/onsv_nacional_geocod.csv": (True, "ONSV geocodificado"),
        "data/processed/sutran_accidentes_geocod.csv": (True, "SUTRAN geocodificado"),
        "data/processed/dataset_modelo.csv": (True, "dataset modelo 3750x40"),
        "data/processed/puntos_negros.csv": (True, "puntos negros"),
        "data/processed/features_distancia.csv": (True, "features distancia"),
        "data/processed/ositran_accidentes.csv": (True, "OSITRAN accidentes"),
        "data/processed/ositran_tramos_geocod.csv": (True, "OSITRAN tramos"),
        "data/processed/ositran_peajes_geo.json": (True, "OSITRAN peajes"),
        "data/processed/ositran_trafico.csv": (True, "OSITRAN tráfico"),
    }
    for path, (required, desc) in assets.items():
        p = ROOT / path
        ok = p.exists()
        size_kb = p.stat().st_size // 1024 if ok else 0
        checks.append({
            "id": f"data:{path}",
            "name": f"Data asset: {desc}",
            "ok": ok,
            "detail": f"{size_kb} KB" if ok else "NO EXISTE",
            "required": required
        })
    return checks

def check_docs():
    checks = []
    docs = {
        "docs/informe_sipat.md": "Informe principal",
        "docs/matriz_tecnica.md": "Matriz técnica",
        "docs/modulo_ruta_segura.md": "Manual módulo ruta segura",
        "docs/figuras/": "Figuras",
    }
    for path, desc in docs.items():
        p = ROOT / path
        ok = p.exists()
        checks.append({
            "id": f"doc:{path}",
            "name": f"Documento: {desc}",
            "ok": ok,
            "detail": "OK" if ok else "NO EXISTE",
            "required": True
        })
    return checks

def check_services():
    checks = []
    services = [
        (5000, "OSRM routing", True),
        (8000, "API FastAPI", True),
        (8501, "Streamlit Dashboard", True),
    ]
    for port, name, required in services:
        ok = check_port(port)
        checks.append({
            "id": f"svc:port{port}",
            "name": f"Servicio: {name} :{port}",
            "ok": ok,
            "detail": "UP" if ok else "DOWN",
            "required": required
        })
    return checks

def check_api_endpoints():
    import urllib.request
    checks = []
    base = "http://localhost:8000"
    endpoints = [
        ("/health", "health"),
        ("/alertas", "alertas SUTRAN"),
        ("/avisos", "avisos SENAMHI+COEN"),
    ]
    for path, name in endpoints:
        try:
            req = urllib.request.Request(f"{base}{path}", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
                ok = r.status == 200
                detail = f"HTTP {r.status}"
                if path == "/health":
                    detail += f" | puntos={data.get('puntos_riesgo','?')} uptime={data.get('uptime_s','?')}s"
                elif path == "/alertas":
                    detail += f" | alertas={len(data)}"
                elif path == "/avisos":
                    detail += f" | senamhi={data.get('senamhi',0)} coen={data.get('coen',0)}"
        except Exception as e:
            ok = False
            detail = str(e)[:120]
        checks.append({
            "id": f"api:{path.strip('/')}",
            "name": f"API endpoint: {name}",
            "ok": ok,
            "detail": detail,
            "required": True
        })
    # POST /ruta_segura_completa
    try:
        body = json.dumps({"origin": "-12.046,-77.028", "dest": "-12.065,-75.204", "include_geometry": False}).encode()
        req = urllib.request.Request(f"{base}/ruta_segura_completa", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
            ok = r.status == 200
            if ok:
                rr = data.get("resumen_riesgo", {})
                hist = rr.get("riesgo_historico", {})
                pred = rr.get("riesgo_predictivo", {})
                clima = data.get("clima", {})
                detail = f"hist={hist.get('score_km','?')} [{hist.get('nivel','?')}] pred={pred.get('siniestros_km','?')} [{pred.get('nivel','?')}] cov={pred.get('cobertura_pct','?')}% clima={clima.get('pronostico') is not None}"
            else:
                detail = f"HTTP {r.status}"
    except Exception as e:
        ok = False
        detail = str(e)[:120]
    checks.append({
        "id": "api:ruta_segura_completa",
        "name": "API POST /ruta_segura_completa (Lima->Huancayo)",
        "ok": ok,
        "detail": detail,
        "required": True
    })
    return checks

def check_dashboard_apptest():
    import subprocess
    script = ROOT / "scripts" / "apptest_check.py"
    if not script.exists():
        return [{
            "id": "dash:apptest",
            "name": "Dashboard AppTest",
            "ok": False,
            "detail": "script apptest_check.py no existe",
            "required": True
        }]
    # Use list form to avoid path splitting issues with spaces
    try:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        detail = (r.stdout or r.stderr or "OK").strip()[-200:]
    except Exception as e:
        ok = False
        detail = str(e)[:200]
    return [{
        "id": "dash:apptest",
        "name": "Dashboard AppTest (7 tabs + Analizar mi ruta)",
        "ok": ok,
        "detail": detail,
        "required": True
    }]

def check_graph():
    checks = []
    g = ROOT / "graphify-out" / "graph.json"
    ok = g.exists()
    detail = ""
    if ok:
        try:
            with open(g, encoding="utf-8") as f:
                data = json.load(f)
            detail = f"nodos={len(data.get('nodes',[]))} enlaces={len(data.get('edges',[]))}"
        except Exception:
            detail = "JSON inválido"
    checks.append({
        "id": "graph:graph_json",
        "name": "Grafo graphify actualizado",
        "ok": ok,
        "detail": detail,
        "required": True
    })
    # vault obsidian
    vault = ROOT / "graphify-out" / "obsidian"
    ok_vault = vault.exists() and any(vault.iterdir())
    detail_vault = f"{len(list(vault.iterdir()))} notas" if ok_vault else "NO EXISTE"
    checks.append({
        "id": "graph:obsidian_vault",
        "name": "Vault Obsidian regenerado",
        "ok": ok_vault,
        "detail": detail_vault,
        "required": True
    })
    return checks

def check_exports():
    """Verifica que existan exportaciones CSV/JSON de rutas de referencia."""
    checks = []
    exp_dir = ROOT / "data" / "processed" / "dashboard"
    routes = [
        ("Lima_Huancayo", "Lima→Huancayo"),
        ("Trujillo_Chiclayo", "Trujillo→Chiclayo"),
    ]
    for slug, name in routes:
        for ext in (".json", ".csv"):
            p = exp_dir / f"ruta_export_{slug}{ext}"
            ok = p.exists()
            checks.append({
                "id": f"export:{slug}{ext}",
                "name": f"Exportación {name} {ext.upper()}",
                "ok": ok,
                "detail": f"{p.stat().st_size//1024} KB" if ok else "NO EXISTE",
                "required": True  # opcional pero parte del criterio de final
            })
    return checks

def check_reports():
    """Verifica reportes HTML de referencia."""
    checks = []
    rep_dir = ROOT / "data" / "processed" / "dashboard"
    routes = [
        ("Lima_Huancayo", "Lima→Huancayo"),
        ("Trujillo_Chiclayo", "Trujillo→Chiclayo"),
    ]
    for slug, name in routes:
        p = rep_dir / f"reporte_{slug}.html"
        ok = p.exists()
        checks.append({
            "id": f"report:{slug}",
            "name": f"Reporte HTML {name}",
            "ok": ok,
            "detail": f"{p.stat().st_size//1024} KB" if ok else "NO EXISTE",
            "required": True
        })
    return checks

def run_all_checks():
    all_checks = []
    all_checks += check_data_assets()
    all_checks += check_docs()
    all_checks += check_services()
    all_checks += check_api_endpoints()
    all_checks += check_dashboard_apptest()
    all_checks += check_graph()
    all_checks += check_exports()
    all_checks += check_reports()
    return all_checks

def _sanitize(s):
    # Replace non-ASCII chars for cp1252 console
    return s.encode("ascii", "replace").decode("ascii")

def print_report(checks):
    print(f"\n{'='*70}")
    print(f" VERIFICACION SIPAT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    passed = sum(1 for c in checks if c["ok"])
    required = sum(1 for c in checks if c["required"])
    required_passed = sum(1 for c in checks if c["ok"] and c["required"])
    for c in checks:
        status = "[PASS]" if c["ok"] else "[FAIL]"
        req = " (req)" if c["required"] else ""
        name = _sanitize(c['name'])
        detail = _sanitize(c['detail'])
        print(f"  {status}{req}  {name}: {detail}")
    print(f"\n  Total: {passed}/{len(checks)} | Requeridos: {required_passed}/{required}")
    print(f"{'='*70}\n")
    return required_passed == required

def main():
    checks = run_all_checks()
    ok = print_report(checks)
    # Guardar reporte JSON
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(checks),
        "passed": sum(1 for c in checks if c["ok"]),
        "required_total": sum(1 for c in checks if c["required"]),
        "required_passed": sum(1 for c in checks if c["ok"] and c["required"]),
        "all_required_ok": ok,
        "checks": checks
    }
    out = ROOT / "data" / "processed" / "dashboard" / "verificacion.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Reporte guardado en: {out}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())