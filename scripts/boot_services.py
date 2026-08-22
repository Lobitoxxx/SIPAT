#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Arranca los 3 servicios SIPAT usando subprocess (evita problemas de PowerShell).
"""
import sys
import os
import subprocess
import time
import socket
import requests
import json

ROOT = r"D:\Proyects\2. Analítica con Big Data\SIPAT"
LOG_DIR = os.path.join(ROOT, "data", "processed", "dashboard")
os.makedirs(LOG_DIR, exist_ok=True)

def test_port(port, host="localhost"):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False

def wait_port(port, timeout=60, label=""):
    for i in range(timeout):
        if test_port(port):
            print(f"[{label}] UP en :{port}")
            return True
        time.sleep(1)
    print(f"[{label}] TIMEOUT esperando puerto {port}")
    return False

def read_log_tail(name, lines=10):
    for ext in (".log", ".err.log"):
        p = os.path.join(LOG_DIR, f"{name}{ext}")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                tail = content.strip().split("\n")[-lines:]
                if tail:
                    print(f"  {name}{ext}: " + " | ".join(tail))
            except Exception:
                pass

def start_osrm():
    print("[OSRM] Verificando Docker...")
    # Check docker
    r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print("[OSRM] Iniciando Docker Desktop...")
        docker_exe = r"C:\Users\D3V1N\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
        subprocess.Popen([docker_exe], creationflags=subprocess.CREATE_NO_WINDOW)
        # Wait for docker
        for i in range(24):
            time.sleep(5)
            r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                print("[OSRM] Docker listo")
                break
        else:
            print("[OSRM] Docker no arrancó")
            return False
    
    print("[OSRM] Arrancando osrm-routed via osrm_build.py --serve...")
    osrm_log = open(os.path.join(LOG_DIR, "osrm_stdout.log"), "w", encoding="utf-8")
    osrm_err = open(os.path.join(LOG_DIR, "osrm_stderr.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "osrm_build.py", "--serve"],
        cwd=os.path.join(ROOT, "scripts"),
        stdout=osrm_log, stderr=osrm_err,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    return wait_port(5000, timeout=60, label="OSRM")

def start_api():
    print("[API] Arrancando FastAPI en :8000...")
    api_log = open(os.path.join(LOG_DIR, "api_stdout.log"), "w", encoding="utf-8")
    api_err = open(os.path.join(LOG_DIR, "api_stderr.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT,
        stdout=api_log, stderr=api_err,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    for i in range(30):
        time.sleep(1)
        if test_port(8000):
            try:
                r = requests.get("http://localhost:8000/health", timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    print(f"[API] UP en :8000 (puntos={data.get('puntos_riesgo','?')} uptime={data.get('uptime_s','?')}s)")
                    return True
            except Exception:
                pass
    print("[API] Timeout o health check falló")
    read_log_tail("api_stderr")
    return False

def start_streamlit():
    print("[DASH] Arrancando Streamlit en :8501...")
    dash_log = open(os.path.join(LOG_DIR, "dash_stdout.log"), "w", encoding="utf-8")
    dash_err = open(os.path.join(LOG_DIR, "dash_stderr.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard/app.py", "--server.port", "8501", "--server.headless", "true"],
        cwd=ROOT,
        stdout=dash_log, stderr=dash_err,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    return wait_port(8501, timeout=60, label="DASH")

def main():
    print("="*60)
    print(" BOOT SIPAT - Iteración 1")
    print("="*60)
    
    ok = True
    
    # OSRM
    if test_port(5000):
        print("[OSRM] Ya UP en :5000")
    else:
        ok = ok and start_osrm()
    
    # API
    if test_port(8000):
        print("[API] Ya UP en :8000")
    else:
        ok = ok and start_api()
    
    # Streamlit
    if test_port(8501):
        print("[DASH] Ya UP en :8501")
    else:
        ok = ok and start_streamlit()
    
    print("="*60)
    if ok:
        print("[OK] Todos los servicios UP")
        return 0
    else:
        print("[FAIL] Algunos servicios no arrancaron")
        return 1

if __name__ == "__main__":
    sys.exit(main())