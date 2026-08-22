"""Explora segmentos del shapefile: rutas, rangos km, cobertura."""
from pathlib import Path

import pandas as pd

SH = Path("data/raw/mtc_datos_espaciales/rvn_dic16/red_vial_nacional_dic16.shp")

import shapefile

sf = shapefile.Reader(str(SH), encoding="iso-8859-1")
fields = [f[0] for f in sf.fields[1:]]
recs = []
for r in sf.iterRecords():
    recs.append(dict(zip(fields, list(r))))

df = pd.DataFrame(recs)
print("SEGMENTOS:", len(df))
print("RUTAS (cCodRutaDi):", df["cCodRutaDi"].nunique())
print("cTipRedDic:", df["cTipRedDic"].value_counts().to_dict())
print("cCodRuta vs cCodRutaDi diferencias:", (df["cCodRuta"] != df["cCodRutaDi"]).sum())
print("\nTop 20 rutas por longitud:")
g = df.groupby("cCodRutaDi").agg(
    seg=("dkmInicio", "size"),
    km_min=("dkmInicio", "min"),
    km_max=("dkmFinal", "max"),
    long=("dLongitud", "sum"),
)
print(g.sort_values("long", ascending=False).head(20).to_string())
print("\nCobertura total km (sum dLongitud):", round(df["dLongitud"].sum(), 1))
print("\nRutas con segmentos solapados/gaps (prueba PE-1N):")
pe1n = df[df["cCodRutaDi"] == "PE-1N"].sort_values("dkmInicio")
print(pe1n[["Id", "dkmInicio", "dkmFinal", "cDepartame", "cClasifica"]].head(15).to_string())
