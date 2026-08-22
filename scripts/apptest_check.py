#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AppTest check para el dashboard. Se ejecuta en proceso separado.
"""
import sys
import os

sys.dont_write_bytecode = True
ROOT = r"D:\Proyects\2. Analítica con Big Data\SIPAT"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import streamlit as st  # noqa: F401
from streamlit.testing.v1 import AppTest

at = AppTest.from_file(os.path.join(ROOT, "dashboard", "app.py"))
at.run(timeout=90)

tabs = [t.label for t in at.tabs]
expected_tabs = 7
if len(tabs) != expected_tabs:
    print(f"FAIL: tabs={len(tabs)} esperado {expected_tabs}: {tabs}")
    sys.exit(1)

pest = None
for t in at.tabs:
    if "Viaja seguro" in t.label:
        pest = t
        break
if pest is None:
    print("FAIL: pestaña 'Viaja seguro' no encontrada")
    sys.exit(1)

btns = [b for b in pest.button if "Analizar" in b.label]
if not btns:
    print("FAIL: botón Analizar no encontrado")
    sys.exit(1)

btns[0].click()
pest.run(timeout=300)

if at.exception:
    for e in at.exception:
        print(f"EXCEPTION: {e.value}")
    sys.exit(1)

if hasattr(pest, "error") and pest.error:
    for e in pest.error:
        print(f"ERROR: {e.value}")
    sys.exit(1)

# Verificar que la ruta se calculó (session_state con resultado)
if "ruta_res" not in at.session_state:
    print("FAIL: ruta_res no quedó en session_state")
    sys.exit(1)

print("OK: Dashboard 7 tabs + Analizar mi ruta -> 0 excepciones")
sys.exit(0)
