"""Analisis temporal y por causa de ONSV (todos los registros 2021-2025)."""
import numpy as np
import pandas as pd

onsv = pd.read_excel("data/raw/onsv/siniestros_fatales_2021-2025.xlsx", sheet_name="SINIESTROS", header=4)
cols = list(onsv.columns)
fecha = [c for c in cols if "FECHA" in c.upper() and "CORTE" not in c.upper()][0]
onsv["fecha"] = pd.to_datetime(onsv[fecha], format="%d/%m/%Y", errors="coerce")
onsv["fal"] = pd.to_numeric(onsv["CANTIDAD DE FALLECIDOS"], errors="coerce")
onsv["les"] = pd.to_numeric(onsv["CANTIDAD DE LESIONADOS"], errors="coerce")
onsv["anio"] = onsv["fecha"].dt.year
onsv["mes"] = onsv["fecha"].dt.month
onsv["dia"] = onsv["fecha"].dt.dayofweek

# horas: la columna HORA puede ser texto
hora_col = [c for c in cols if c.upper() == "HORA SINIESTRO"]
hora = pd.to_numeric(onsv[hora_col[0]].astype(str).str.replace(":", ".", 1), errors="coerce") if hora_col else None

print("== Total periodo ==")
print(f"siniestros: {len(onsv)}   fallecidos: {onsv['fal'].sum():.0f}   lesionados: {onsv['les'].sum():.0f}")

print("\n== Por anio (siniestros / fallecidos / fallecidos por siniestro) ==")
g = onsv.groupby("anio").agg(n=("fecha", "size"), fal=("fal", "sum"), les=("les", "sum"))
g["fal_x_sin"] = g["fal"] / g["n"]
print(g.round(2).to_string())

print("\n== Por mes (promedio siniestros/dia, 2021-2024 excluyendo 2025 parcial) ==")
d = onsv[onsv["anio"] < 2025]
mg = d.groupby(["anio", "mes"]).size().unstack(0).mean(axis=1)
print(mg.round(1).to_string())

print("\n== Por dia de semana (lun=0) ==")
print(onsv.groupby("dia").size().sort_index().to_string())

print("\n== HORA SINIESTRO (agrupada por rango de 3h) ==")
if hora is not None:
    onsv["hora3"] = (hora // 3) * 3
    print(onsv.groupby("hora3").size().to_string())

print("\n== CLASE SINIESTRO ==")
print(onsv["CLASE SINIESTRO"].value_counts().head(8).to_string())

print("\n== CAUSA FACTOR PRINCIPAL ==")
causa = [c for c in cols if "CAUSA" in c.upper()]
print(onsv[causa[0]].value_counts().head(10).to_string())

print("\n== CONDICION CLIMATICA ==")
clima = [c for c in cols if "CONDICI" in c.upper()]
print(onsv[clima[0]].value_counts().head(6).to_string())

print("\n== SUPERFICIE DE CALZADA ==")
sup = [c for c in cols if "SUPERFICIE" in c.upper()]
print(onsv[sup[0]].value_counts().head(6).to_string())

print("\n== SEÑAL VERTICAL / HORIZONTAL (nacional) ==")
sv = [c for c in cols if "SE" in c.upper() and "EXISTE" in c.upper()]
for c in sv:
    print(f"{c}: {onsv[c].value_counts().head(4).to_dict()}")
