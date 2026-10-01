# -*- coding: utf-8 -*-
"""Tests de las figuras embebidas en los HTML del pipeline.

Dos motives:

1. Que el reporte de calidad y el perfil `after` incluyan las imágenes. Son la
   forma más barata de explicar el DQS y la limpieza sin que nadie tenga que
   abrir `docs/figuras/etl/`.

2. Que esas figuras NO se escriban como PNG sueltos en `docs/figuras/etl/`.
   Ahí viven las figuras comparativas de `scripts/graficos_etl.py`, con los dos
   datasets; si el pipeline escribiera `dqs_dimensiones.png` con un único
   dataset, lo pisaría. Es el mismo defecto que ya se corrigió en
   `scripts/graficos_etl.py` con el sufijo de dataset, repetido por descuido en
   la otra ruta.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from src.profiling.profile import profile
from src.reports.report import generate_quality_report

DQS = {
    "dqs": 92.07,
    "dimensions": {
        "completeness": 100.0, "uniqueness": 100.0, "validity": 95.0,
        "consistency": 96.0, "accuracy": 90.0, "freshness": 65.0,
    },
    "weights": {
        "completeness": 0.25, "uniqueness": 0.15, "validity": 0.25,
        "consistency": 0.15, "accuracy": 0.10, "freshness": 0.10,
    },
}

B64_IMG = re.compile(r'data:image/png;base64,[A-Za-z0-9+/=]{100,}')


@pytest.fixture(autouse=True)
def _requires_mpl():
    from src.quality import figures as F

    if not F.available():
        pytest.skip("matplotlib no disponible")


def test_quality_report_embeds_figures_without_writing_pngs(tmp_path: Path):
    report_dir = tmp_path / "quality"
    figures_dir = Path("docs/figuras/etl")
    before_png = {p.name for p in figures_dir.glob("*.png")} if figures_dir.exists() else set()

    out = generate_quality_report(
        "onsv", "run-test-0001", {"status": "PASSED", "dqs": 92.07},
        out_dir=report_dir, dqs=DQS,
    )
    html = out.read_text(encoding="utf-8")

    assert B64_IMG.search(html), "el reporte debe incrustar al menos una figura"
    # Dos figuras: DQS por dimensión y nulos antes/después.
    assert len(B64_IMG.findall(html)) >= 2
    assert "<h2>Figuras</h2>" in html
    # El reporte sigue siendo autocontenido: sin src="...png" externo.
    assert not re.search(r'<img[^>]+src="(?!data:)', html)

    after_png = {p.name for p in figures_dir.glob("*.png")} if figures_dir.exists() else set()
    assert after_png == before_png, (
        "el pipeline no debe escribir PNG en docs/figuras/etl/ (pisaría las "
        "comparativas de graficos_etl.py)"
    )


def test_quality_report_without_dqs_is_still_valid_html(tmp_path: Path):
    """Degradar, no romper: sin `dqs` el reporte sale igual, solo sin figuras."""
    out = generate_quality_report(
        "onsv", "run-test-0002", {"status": "PASSED", "dqs": 92.07},
        out_dir=tmp_path / "q2",
    )
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "<h2>Quality Gate</h2>" in html
    assert "data:image/png" not in html


def test_after_profile_embeds_comparative_figure(tmp_path: Path):
    before = pd.DataFrame({
        "codigo": [1, 2, 3, 4],
        "fecha": ["2025-01-01"] * 4,
        "distrito": ["lima", "cusco", None, "arequipa"],
        "vehiculos_danados": [1, None, None, None],
        "carril": [None, None, None, None],  # columna que la limpieza no arregla
    })
    after = before.copy()
    after["distrito"] = before["distrito"].fillna("SIN DATO")
    after["vehiculos_danados"] = before["vehiculos_danados"].fillna(2)
    # `carril` sigue 100 % nula: es lo que la figura debe dejar visible.

    profile(before, "onsv", "before", report_dir=tmp_path)
    profile(after, "onsv", "after", report_dir=tmp_path)

    after_html = (tmp_path / "onsv_after_profile.html").read_text(encoding="utf-8")
    before_html = (tmp_path / "onsv_before_profile.html").read_text(encoding="utf-8")

    assert B64_IMG.search(after_html), "el perfil 'after' debe mostrar la comparación"
    assert "siguen casi vacías" in after_html, (
        "la figura debe advertir de las columnas que la limpieza no pudo arreglar"
    )
    assert not B64_IMG.search(before_html), (
        "en el perfil 'before' todavía no hay con qué comparar: no debe figurar"
    )
    assert not list(tmp_path.glob("*.png")), "el perfil no debe dejar PNG sueltos"


def test_after_profile_without_before_does_not_fail(tmp_path: Path):
    after = pd.DataFrame({"codigo": [1, 2], "distrito": ["lima", None]})
    profile(after, "onsv", "after", report_dir=tmp_path)
    html = (tmp_path / "onsv_after_profile.html").read_text(encoding="utf-8")
    assert "<table>" in html and html.strip().endswith("</html>")