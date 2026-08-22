"""Auditoría técnica de un archivo de datos: estructura, calidad y cobertura."""
import sys
from pathlib import Path

import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)

ENCODINGS = ["utf-8-sig", "cp1252", "latin-1"]


def detect_encoding(path: str) -> str:
    raw = Path(path).read_bytes()[:400000]
    for enc in ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def detect_sep(path: str, enc: str) -> str:
    for line in Path(path).open(encoding=enc, errors="replace"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return ";" if line.count(";") >= line.count(",") else ","
    return ","


def audit(path: str) -> None:
    p = Path(path)
    print("=" * 90)
    print(f"ARCHIVO: {p.name}  ({p.stat().st_size:,} bytes)")
    print("=" * 90)

    suffix = p.suffix.lower()
    if suffix in (".csv", ".txt"):
        enc = detect_encoding(path)
        sep = detect_sep(path, enc)
        print(f"Encoding: {enc}   Separador: {sep!r}")
        try:
            df = pd.read_csv(p, low_memory=False, encoding=enc, sep=sep)
        except UnicodeDecodeError:
            print("-> fallback: lectura con latin-1 (errors=replace)")
            df = pd.read_csv(
                p, low_memory=False, encoding="latin-1", sep=sep,
                on_bad_lines="warn",
            )
    elif suffix in (".xls", ".xlsx"):
        df = pd.read_excel(p)
    else:
        print("Formato no soportado")
        return

    print(f"\nRegistros: {len(df):,}   Columnas: {df.shape[1]}")
    print("\nColumnas y dtypes:")
    for c in df.columns:
        print(f"  {c!r:40s} -> {df[c].dtype}")

    print("\nCalidad (nulos / únicos / % nulo):")
    for c in df.columns:
        n_null = int(df[c].isna().sum())
        n_uniq = df[c].nunique()
        pct = 100 * n_null / len(df) if len(df) else 0
        flag = "  <-- REVISAR" if pct > 10 else ""
        print(f"  {c!r:40s} nulos={n_null:8,} ({pct:5.1f}%)  unicos={n_uniq:8,}{flag}")

    print("\nPrimeras 5 filas:")
    print(df.head().to_string())

    # Inferencia de cobertura temporal si hay columnas de fecha
    for c in df.columns:
        if any(k in c.lower() for k in ("fecha", "date", "hora", "mes", "anio", "año")):
            try:
                s = pd.to_datetime(df[c], errors="coerce").dropna()
                if len(s):
                    print(f"\nCobertura temporal en '{c}': {s.min()} -> {s.max()}")
            except Exception:
                pass
            break

    print("\n")


if __name__ == "__main__":
    audit(sys.argv[1])
