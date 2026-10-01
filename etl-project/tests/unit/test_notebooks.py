# -*- coding: utf-8 -*-
"""Tests de los notebooks del ETL.

Los notebooks se GENERAN con `scripts/build_notebooks.py` (no se editan a mano),
así que estos tests vigilan tres cosas:

1. Que el build produzca notebooks válidos: JSON correcto, celdas con `id`
   (nbformat >= 4.5 lo exige), sin celdas de código que fallen al compilar y sin
   salidas, para no versionar ni pesos ni resultados rancios.

2. Que los `.ipynb` del repo no se editen a mano: sus fuentes deben coincidir
   exactamente con las que produce el builder.

3. Que el notebook 04 de confiabilidad no vuelva a imprimir etiquetas
   engañosas. Es la regresión de este trabajo:
     - la celda de cobertura imprimía `cov['rango_anios']` etiquetado como "años",
       cuando `rango_anios` solo tiene los dos extremos del rango y el reparto
       está en `cov['anios']`;
     - la de consistencia cruzada leía `n_a`, `n_b` y `n_interseccion`, claves
       que `cross_dataset` no define: imprimía "onsv (0 valores) vs
       cinemometros (0 valores)", y un cero ahí parece un dato medido en cero
       cuando en realidad es una clave mal escrita (lo correcto son
       `valores_a`, `valores_b` y `valores_comunes`);
     - la de deriva rotulaba `dqs_min`/`dqs_max` como "en la huella" cuando
       venían de todas las huellas, y se confundía un cambio de método con deriva.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

NOTEBOOKS_DIR = Path("notebooks")
EXPECTED = {
    "01_exploracion_onsv.ipynb",
    "02_exploracion_cinemometros.ipynb",
    "03_silver_dqs_gate.ipynb",
    "04_auditoria_medicion.ipynb",
}
NB04 = "04_auditoria_medicion.ipynb"


@pytest.fixture(scope="module")
def build_all() -> Dict[str, Dict[str, Any]]:
    """Construye los notebooks en un temporal y devuelve {nombre: notebook}."""
    import scripts.build_notebooks as B

    tmp = Path(pytest.importorskip("tempfile").mkdtemp(prefix="nb_build_"))
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in B.build_all(tmp)}


def _sources(nb: Dict[str, Any], cell_type: str) -> str:
    return "\n".join(
        "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == cell_type
    )


def test_builder_creates_every_notebook(build_all):
    assert set(build_all) == EXPECTED, (
        f"faltan o sobran notebooks: {sorted(set(EXPECTED) ^ set(build_all))}"
    )


def test_notebooks_are_valid_nbformat(build_all):
    nbformat = pytest.importorskip("nbformat")
    for name, nb in build_all.items():
        nbformat.validate(nbformat.reads(json.dumps(nb), as_version=4))
        assert nb["metadata"]["kernelspec"]["language"], f"{name} sin kernelspec"


def test_notebooks_ship_without_outputs(build_all):
    """Se versionan limpios; para verlos renderizados:
    `python scripts/build_notebooks.py --execute`."""
    for name, nb in build_all.items():
        for i, cell in enumerate(nb["cells"]):
            assert cell.get("outputs", []) == [], f"{name} celda {i} trae outputs"
            assert cell.get("execution_count") is None, (
                f"{name} celda {i} trae execution_count"
            )


def test_all_code_cells_compile(build_all):
    """`validate()` del builder ya lo comprueba, pero aquí se confirma que el
    fallo se detectaría también desde los tests."""
    for name, nb in build_all.items():
        for i, cell in enumerate(nb["cells"]):
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), f"{name}#cell{i}", "exec")


def test_cell_ids_are_unique(build_all):
    """nbformat >= 4.5 exige `id` y no puede repetirse; el builder numera las
    celdas precisamente para poder reescribir una sin duplicarla."""
    for name, nb in build_all.items():
        ids = [c["id"] for c in nb["cells"]]
        assert len(ids) == len(set(ids)), f"{name} tiene ids duplicados"
        assert all(i for i in ids), f"{name} tiene celdas sin id"


def test_repo_notebooks_are_not_hand_edited(build_all):
    """Si el .ipynb del repo difiere del builder, alguien lo editó a mano o el
    build quedó a medias. Las salidas se permiten (son un artefacto de
    ejecución), las fuentes no."""
    for name in EXPECTED:
        on_disk = json.loads((NOTEBOOKS_DIR / name).read_text(encoding="utf-8"))
        built = build_all[name]
        assert [c["source"] for c in on_disk["cells"]] == [
            c["source"] for c in built["cells"]
        ], f"{name} del repo difiere de scripts/build_notebooks.py"


def test_auditoria_notebook_reads_only_real_keys(build_all):
    """Ninguna de las claves que la celda imprime puede existir."""
    src = _sources(build_all[NB04], "code")
    for clave in ("n_a", "n_b", "n_interseccion"):
        assert f"'{clave}'" not in src and f'"{clave}"' not in src, (
            f"la celda lee '{clave}', que cross_dataset/coverage_profile no definen"
        )
    # Las claves que sí existen y hay que usar.
    for clave in ("frac_anio_modal_pct", "valores_comunes", "solo_en_a", "valores_a"):
        assert clave in src, f"el notebook debe usar '{clave}'"


def test_auditoria_notebook_labels_are_not_misleading(build_all):
    src = _sources(build_all[NB04], "code")
    assert "rango_anios" not in src, (
        "rango_anios solo tiene los dos extremos: no puede ir etiquetado como 'años'"
    )
    assert "cov['anios']" in src, "el reparto por año se lee de coverage['anios']"
    # Extremos globales y extremos de la huella vigente, distinguidos.
    assert "dqs_min_huella_vigente" in src
    assert "TODAS las huellas" in src
    assert "huella vigente" in src


def test_auditoria_notebook_declares_dqs_is_not_reliability(build_all):
    """La idea que sostiene el módulo: el DQS no se lee como probabilidad de que
    los datos sean ciertos, y la auditoría tampoco se colapsa en un número.

    Además el notebook tiene que separar las cuatro preguntas del proyecto: si
    vuelve a llamarse "confiabilidad" sin más, vuelve a ser ambiguo."""
    md = _sources(build_all[NB04], "markdown")
    assert "Auditoría de la medición" in md
    assert "audita **las métricas" in md or "audita las **métricas" in md
    assert "No se calcula un" in md and "índice de confiabilidad" in md, (
        "el notebook debe dejar escrito que no hay un score único"
    )
    assert "score de confiabilidad" not in md.lower()
    # Las otras dos auditorías deben existir nombradas, para que "confiabilidad"
    # no vuelva a ser un cajón de sastre.
    assert "Fiabilidad de las fuentes" in md
    assert "Validez predictiva" in md
    # Y debe cubrir los dos mecanismos que hacen el DQS no determinista, más el
    # que lo hace circular: incertidumbre, robustez a pesos y circularidad.
    for eje in ("Incertidumbre", "Robustez", "Circularidad", "Cobertura"):
        assert eje in md, f"falta el eje {eje} en la tabla de afirmaciones"
    assert "bootstrap" in md.lower()


def test_auditoria_notebook_embeds_figures_as_base64(build_all):
    """Con el backend Agg, `plt.show()` no renderiza nada: las figuras viajan
    como PNG decodificado a `display(Image(...))`, que sí produce salida en el
    .ipynb."""
    src = _sources(build_all[NB04], "code")
    assert "_b64.b64decode" in src, "la figura debe ir embebida en base64"
    assert "display(_Image(" in src
    assert "_show(" in src, "las celdas de figuras deben pasar por _show()"


def _plt_show_calls(nb: Dict[str, Any]) -> list:
    """Llamadas REALES a plt.show(), no menciones dentro de docstrings.

    El docstring de `_show` explica justamente por qué no se usa, así que
    buscar la cadena a pelo daría un falso positivo. Se mira el AST.
    """
    import ast

    hits = []
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        for node in ast.walk(ast.parse("".join(cell["source"]))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "show"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "plt"
            ):
                hits.append(i)
    return hits


def test_auditoria_notebook_never_calls_plt_show(build_all):
    """Con Agg, plt.show() no produce salida: las figuras se incrustan con
    display(Image(...)). Si alguien lo reintroduce, las celdas de figuras salen
    vacías sin ningún error visible."""
    assert _plt_show_calls(build_all[NB04]) == []