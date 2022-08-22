# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import pytest

from gingerbread import trace
from .utils import compare_footprints, RESOURCES


@pytest.mark.parametrize(
    "name",
    [
        "square-50x50mm",
        "black-white-squares-10x10mm",
        "square-holes-50x50mm",
        "square-nested-holes-50x50mm",
        "complex-50x50mm",
    ],
)
def test_trace(name):
    fp = trace.trace(RESOURCES / f"{name}-254dpi.png", dpi=254)
    assert compare_footprints(RESOURCES / f"{name}.kicad_mod", fp)


def test_square_not_centered():
    fp = trace.trace(RESOURCES / "square-50x50mm-254dpi.png", dpi=254, center=False)
    assert compare_footprints(RESOURCES / "square-50x50mm-not-centered.kicad_mod", fp)


@pytest.mark.parametrize("threshold", [25, 100, 150, 200, 250])
def test_square_grays(threshold):
    fp = trace.trace(
        RESOURCES / "grays-10x10mm-254dpi.png", dpi=254, threshold=threshold
    )
    assert compare_footprints(
        RESOURCES / f"grays-10x10mm-thresh-{threshold}.kicad_mod", fp
    )


def test_black_and_white_squares_inverted():
    fp = trace.trace(
        RESOURCES / "black-white-squares-10x10mm-254dpi.png", dpi=254, invert=True
    )
    assert compare_footprints(
        RESOURCES / "black-white-squares-10x10mm-inverted.kicad_mod", fp
    )
