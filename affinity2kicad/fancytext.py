# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import os.path

import cairocffi
import rich
import rich.box
import rich.panel
import rich.text

from .bitmap2component import bitmap2component
from .document import SVGDocument

DPI = 2540
DPMM = 25.4 / DPI
MMPX = DPI / 25.4
_ALIGN_MAPPING = {
    "start": "left",
    "middle": "center",
    "end": "right",
}

console = rich.get_console()


def _get_text_extents(text, font, size):
    surface = cairocffi.RecordingSurface(cairocffi.CONTENT_COLOR_ALPHA, None)
    context = cairocffi.Context(surface)

    with context:
        context.select_font_face(
            font, cairocffi.FONT_SLANT_NORMAL, cairocffi.FONT_WEIGHT_NORMAL
        )
        context.set_font_size(size)

        return context.text_extents(text)


class FancyText:
    def __init__(self, size=2, font="sans", align="middle", line_spacing=1):
        self.size = size
        self.font = font
        self.align = align
        self.line_spacing = line_spacing
        self.bbox = [0, 0, 0, 0]

    def generate(self, text, layer="F.SilkS"):
        workdir = os.path.join(".", ".cache")
        png_path = os.path.join(workdir, "fancytext.png")
        mod_path = os.path.join(workdir, "fancytext.kicad_mod")
        flip = layer in ("B.SilkS", "B.Cu", "B.Mask")

        svg = SVGDocument(
            text=self._generate_svg(text, flip=flip),
            dpi=DPI,
        )

        svg.render(png_path)

        bitmap2component(src=png_path, dst=mod_path, layer=layer, invert=True, dpi=DPI)

        console.print(
            f"Generated fancytext with W: {self.bbox[2]:.1f} mm, H: {self.bbox[3]:.1f} mm:"
        )

        console.print(
            rich.panel.Panel.fit(
                rich.text.Text(text, justify=_ALIGN_MAPPING[self.align]),
                style="green",
                safe_box=False,
                border_style="grey23",
            )
        )
        console.print()

        return mod_path

    def _generate_svg(self, text, flip=False):
        size_px = self.size * MMPX
        transforms = []
        width = 0
        height = 0
        x = 0
        y = 0

        spans = []
        lines = text.split("\n")

        for n, line in enumerate(lines):
            (_, y_bearing, w, h, _, _) = _get_text_extents(line, self.font, self.size)
            width = max(width, w)

            if n > 0:
                height += self.size * self.line_spacing
            else:
                height += self.size

            dy = f"{self.line_spacing}em" if n else f"{abs(y_bearing) * MMPX}px"
            spans.append(
                f"""<tspan x="0" dy="{dy}" style="text-anchor: {self.align};">{line}</tspan>"""
            )

        self.bbox = [x, y, width, height]
        width_px = (width + 2) * MMPX
        height_px = (height + 2) * MMPX
        x_px = 1 * MMPX
        y_px = 1 * MMPX

        if self.align == "middle":
            transforms.append(f"translate({width_px / 2:.0f}px, 0)")

        if flip:
            transforms.append("scale(-1, 1)")

        if transforms:
            transform = f"transform: {' '.join(transforms)};"
        else:
            transform = ""

        return f"""\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="100%" height="100%" viewBox="0 0 {width_px} {height_px}" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve">
    <text x="{x_px}" y="{y_px}" style="font-size: {size_px}px; font-family: {self.font}; {transform}">
        {"".join(spans)}
    </text>
</svg>"""
