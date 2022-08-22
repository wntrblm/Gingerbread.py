# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import pytest

from gingerbread import fancytext
from .utils import compare_footprints, RESOURCES


@pytest.mark.parametrize(
    ["filename", "text", "kwargs"],
    [
        # The basics
        ("fancytext-hello-world.kicad_mod", "Hello, World!", dict()),
        ("fancytext-hello-world-bold.kicad_mod", "Hello, World!", dict(bold=True)),
        ("fancytext-hello-world-italic.kicad_mod", "Hello, World!", dict(italic=True)),
        ("fancytext-hello-world-bold-italic.kicad_mod", "Hello, World!", dict(bold=True, italic=True)),
        ("fancytext-hello-world-strikethrough.kicad_mod", "Hello, World!", dict(strikethrough=True)),
        ("fancytext-hello-world-underline.kicad_mod", "Hello, World!", dict(underline=True)),
        ("fancytext-hello-world-overline.kicad_mod", "Hello, World!", dict(overline=True)),
        ("fancytext-hello-world-stroke-1.kicad_mod", "Hello, World!", dict(stroke_mm=1)),
        ("fancytext-hello-world-size-5.kicad_mod", "Hello, World!", dict(size_mm=5)),
        ("fancytext-hello-world-helvetica.kicad_mod", "Hello, World!", dict(font="Helvetica")),
        # Multi-line
        ("fancytext-luke-skywalker-multiline.kicad_mod", "Luke\nSkywalker", dict()),
        ("fancytext-luke-skywalker-multiline-left.kicad_mod", "Luke\nSkywalker", dict(align="left")),
        ("fancytext-luke-skywalker-multiline-right.kicad_mod", "Luke\nSkywalker", dict(align="right")),
        ("fancytext-luke-skywalker-multiline-line-spacing-0.5.kicad_mod", "Luke\nSkywalker", dict(line_spacing=0.5)),
        # Outlining
        ("fancytext-hello-world-outline-stroke-1.kicad_mod", "Hello, World!", dict(outline_stroke_mm=1)),
        ("fancytext-hello-world-outline-stroke-2.kicad_mod", "Hello, World!", dict(outline_stroke_mm=2)),
        ("fancytext-hello-world-outline-stroke-1-padding-3-3.kicad_mod", "Hello, World!", dict(outline_stroke_mm=1, padding_mm=(3, 3))),
        ("fancytext-hello-world-outline-fill.kicad_mod", "Hello, World!", dict(outline_stroke_mm=1, outline_fill=True)),
        ("fancytext-hello-world-outline-fill-padding-3-3.kicad_mod", "Hello, World!", dict(outline_stroke_mm=1, outline_fill=True, padding_mm=(3, 3))),
    ],
)
def test_fancytext(filename, text, kwargs):
    fp = fancytext.generate(text=text, **kwargs)

    if not (RESOURCES / filename).exists():
        (RESOURCES / filename).write_text(fp)

    compare_footprints(RESOURCES / filename, fp)
