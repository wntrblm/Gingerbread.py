# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import argparse
import contextlib
from math import sqrt
import os.path
import shlex
import sys
import shutil
import tempfile
import atexit

import cairocffi
from rich import print

from .bitmap2component import bitmap2component
from .document import SVGDocument


_ALIGN = {
    "left": "start",
    "center": "middle",
    "right": "end",
}


@contextlib.contextmanager
def _temporary_font_context(font, size, bold, italic):
    surface = cairocffi.RecordingSurface(cairocffi.CONTENT_COLOR_ALPHA, None)
    context = cairocffi.Context(surface)

    with context:
        context.select_font_face(
            font,
            cairocffi.FONT_SLANT_ITALIC if italic else cairocffi.FONT_SLANT_NORMAL,
            cairocffi.FONT_WEIGHT_BOLD if bold else cairocffi.FONT_WEIGHT_NORMAL,
        )
        context.set_font_size(size)

        yield context


def _get_font_extents(font, size, bold, italic):
    with _temporary_font_context(font, size, bold, italic) as context:
        return context.font_extents()


def _get_text_extents(text, font, size, bold, italic):
    with _temporary_font_context(font, size, bold, italic) as context:
        return context.text_extents(text)


class Style:
    def preprocess(self, text):
        return text

    def apply(self, text):
        pass

    def toxml_before(self):
        return ""

    def toxml_after(self):
        return ""


class BoxStyle:
    def __init__(self, padding=[50, 50], left="(", right=")"):
        self.padding = padding
        self.left = left
        self.right = right
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0

    def preprocess(self, text: str):
        if text.startswith(("[", "(", "<", "/", "\\")):
            self.left = text[0]
            text = text[1:]
        if text.endswith(("]", ")", ">", "/", "\\")):
            self.right = text[-1]
            text = text[0:-1]
        return text

    def apply(self, text):
        self.x = -self.padding[0]
        self.y = -self.padding[0]
        self.width = text.width_px + self.padding[0] * 2
        self.height = text.y_bearing_px + self.padding[1] * 2
        text.fill = "white"

    def toxml_before(self):
        rects = []

        padhalf = self.padding[0] / 2
        pad1 = self.padding[0]
        pad2 = self.padding[0] * 2
        slice_w = self.width / 2
        center = self.x + (self.width / 2)
        right = self.x + self.width

        rects.append(
            f'<rect x="{center - slice_w / 2}" y="{self.y}" width="{slice_w}" height="{self.height}" />'
        )
        rects.append(
            f'<rect x="{center - slice_w / 2}" y="{self.y}" width="{slice_w}" height="{self.height}" />'
        )

        if self.left == "[":
            rects.append(
                f'<rect x="{self.x}" y="{self.y}" width="{slice_w}" height="{self.height}" />'
            )
        if self.right == "]":
            rects.append(
                f'<rect x="{center}" y="{self.y}" width="{slice_w}" height="{self.height}" />'
            )

        radius = self.height * 0.5
        if self.left == "(":
            rects.append(
                f'<rect x="{self.x}" y="{self.y}" width="{slice_w}" height="{self.height}" rx="{radius}" />'
            )
        if self.right == ")":
            rects.append(
                f'<rect x="{right - slice_w}" y="{self.y}" width="{slice_w}" height="{self.height}" rx="{radius}" />'
            )

        if self.left == "/":
            rects.append(
                f'<rect x="{self.x}" y="{self.y}" width="{slice_w}" height="{self.height}" transform="skewX(-20)" />'
            )
        if self.right == "/":
            rects.append(
                f'<rect x="{center + pad1}" y="{self.y}" width="{slice_w}" height="{self.height}" transform="skewX(-20)" />'
            )

        if self.left == "\\":
            rects.append(
                f'<rect x="{self.x - padhalf}" y="{self.y}" width="{slice_w + padhalf}" height="{self.height}" transform="skewX(20)" />'
            )
        if self.right == "\\":
            rects.append(
                f'<rect x="{center}" y="{self.y}" width="{slice_w}" height="{self.height}" transform="skewX(20)" />'
            )

        hyp = self.height / sqrt(2)
        if self.left == "<":
            rects.append(
                f'<rect x="{self.x + pad1}" y="{self.y}" width="{slice_w / 2}" height="{self.height}" />'
            )
            rects.append(
                f'<rect x="0" y="0" width="{hyp}" height="{hyp}" transform="translate({self.x + pad1}, {self.y}) rotate(45)" />'
            )
        if self.right == ">":
            rects.append(
                f'<rect x="{center}" y="{self.y}" width="{slice_w}" height="{self.height}" />'
            )
            rects.append(
                f'<rect x="0" y="0" width="{hyp}" height="{hyp}" transform="translate({self.x + self.width}, {self.y}) rotate(45)" />'
            )

        return "\n".join(rects)

    def toxml_after(self):
        pass


class OutlineStyle:
    def __init__(self, padding=[100, 100]):
        self.padding = padding
        self.border_width = 0
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0

    def preprocess(self, text: str):
        return text

    def apply(self, text):
        self.x = -self.padding[0]
        self.y = -self.padding[0]
        self.width = text.width_px + self.padding[0] * 2
        self.height = text.y_bearing_px + self.padding[1] * 2
        self.border_width = text.size * 10

    def toxml_before(self):
        return f'<rect x="{self.x}" y="{self.y}" width="{self.width}" height="{self.height}" stroke="black" stroke-width="{self.border_width}" fill="transparent" />'

    def toxml_after(self):
        pass


class _Text:
    def __init__(
        self,
        *,
        text,
        font,
        mmpx,
        bold=False,
        italic=False,
        size=2,
        line_spacing=1.5,
        align="center",
        flip=False,
        fill="black",
        stroke="white",
        stroke_width=0,
    ):
        self.text = text
        self.size = size
        self.bold = bold
        self.italic = italic
        self.line_spacing = line_spacing
        self.font = font
        self.align = align
        self.flip = flip
        self.fill = fill
        self.stroke = stroke
        self.stroke_width = stroke_width
        self.mmpx = mmpx

        self._generate_spans()

    def _generate_spans(self):
        self.spans = []

        align = _ALIGN[self.align]
        lines = self.text.split("\n")
        width = 0
        height = 0
        total_y_bearing = 0

        (
            font_ascent,
            font_descent,
            font_height,
            _,
            font_max_y_advance,
        ) = _get_font_extents(
            font=self.font, size=self.size, bold=self.bold, italic=self.italic
        )
        # print(f"{font_ascent=}, {font_descent=}, {font_height=}, {font_max_y_advance=}")

        for n, line in enumerate(lines):
            (_, y_bearing, line_w, line_h, _, _) = _get_text_extents(
                line, font=self.font, size=self.size, bold=self.bold, italic=self.italic
            )
            width = max(width, line_w)

            line_spacing = 1 if n == 0 else self.line_spacing

            if n == len(lines) - 1:
                height += line_h * line_spacing
            else:
                height += abs(y_bearing) * line_spacing

            total_y_bearing += font_ascent / 2 * line_spacing

            dy = f"{font_ascent / 2 * line_spacing * self.mmpx}px"
            self.spans.append(
                f"""<tspan x="0" dy="{dy}" style="text-anchor: {align};">{line}</tspan>"""
            )

        self.size_px = self.size * self.mmpx
        self.width_px = width * self.mmpx
        self.height_px = height * self.mmpx
        self.y_bearing_px = total_y_bearing * self.mmpx
        self.x_px = 0
        self.y_px = 0

    def _combine_transforms(self):
        transforms = []
        if self.align == "center":
            transforms.append(f"translate({self.width_px / 2:.0f}px, 0)")

        if self.flip:
            transforms.append("scale(-1, 1)")

        if transforms:
            transform = f"transform: {' '.join(transforms)};"
        else:
            transform = ""

        return transform

    def _text_style(self):
        style = f"font-family: {self.font}; " f"font-size: {self.size_px}px; "

        if self.bold:
            style = f"{style} font-weight: bold;"

        if self.italic:
            style = f"{style} font-style: italic;"

        return style

    def _paint_style(self):
        style = (
            f"fill: {self.fill}; "
            f"stroke: {self.stroke}; "
            f"stroke-width: {self.stroke_width}; "
        )

        return style

    def toxml(self):
        return f"""
        <text x="{self.x_px}" y="{self.y_px}" style="{self._text_style()} {self._combine_transforms()} {self._paint_style()}">
            {"".join(self.spans)}
        </text>"""


def _generate_svg(*, text, padding, dpi, style, **kwargs):
    mmpx = dpi / 25.4

    text = style.preprocess(text)
    text_gen = _Text(text=text, mmpx=mmpx, **kwargs)
    style.apply(text_gen)

    svg_x = padding[0] * mmpx
    svg_y = padding[1] * mmpx
    svg_width = text_gen.width_px + (padding[0] * 2 * mmpx)
    svg_height = text_gen.height_px + (padding[1] * 2 * mmpx)

    return f"""\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="100%" height="100%" viewBox="0 0 {svg_width} {svg_height}" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve">
<g style="transform: translate({svg_x}px, {svg_y}px)">
    {style.toxml_before()}
    {text_gen.toxml()}
    {style.toxml_after()}
</g>
</svg>"""


def generate(
    *,
    text,
    layer="F.SilkS",
    padding=[2, 2],
    dpi=2540,
    style=Style(),
    comment="",
    **kwargs,
):
    flip = layer.startswith("B.")

    workdir = tempfile.mkdtemp()
    atexit.register(lambda path: shutil.rmtree(path), workdir)

    png_path = os.path.join(workdir, "fancytext.png")
    mod_path = os.path.join(workdir, "fancytext.kicad_mod")

    svg = SVGDocument(
        text=_generate_svg(
            text=text, flip=flip, padding=padding, dpi=dpi, style=style, **kwargs
        ),
        dpi=dpi,
    )

    with open(os.path.join(workdir, "fancytext.svg"), "w") as fh:
        fh.write(svg.tostring())

    svg.render(png_path)

    bitmap2component(src=png_path, dst=mod_path, layer=layer, invert=True, dpi=dpi)

    with open(mod_path, "r") as fh:
        mod_text = fh.read()

    mod_text = mod_text.replace(
        "(module LOGO ",
        (
            '(footprint "LOGO" (version 20211014) (generator pcbnew) '
            "(attr board_only exclude_from_pos_files exclude_from_bom) "
            f'(fp_text user "{comment}" (at 0 0 unlocked) (layer "F.Fab") hide '
            "    (effects (font (size 0.7 0.7) (thickness 0.15)))"
            "    (tstamp 5fc858c7-d6ee-480d-8735-c54b7e2ea66a))"
        ),
    )

    return mod_text


def main():
    import pyperclip

    parser = argparse.ArgumentParser()

    parser.add_argument("--font", default="Space Mono")
    parser.add_argument("--bold", action=argparse.BooleanOptionalAction)
    parser.add_argument("--italic", action=argparse.BooleanOptionalAction)
    parser.add_argument("--size", type=float, default=2)
    parser.add_argument("--stroke-width", type=float, default=0)
    parser.add_argument("--line-spacing", type=float, default=1.5)
    parser.add_argument(
        "--align", default="center", choices=["left", "center", "right"]
    )
    parser.add_argument("--layer", default=None)
    parser.add_argument("--back-silk", action="store_true")
    parser.add_argument("--front-copper", action="store_true")
    parser.add_argument("--back-copper", action="store_true")
    parser.add_argument("--dpi", type=int, default=2540)
    parser.add_argument("--style", default="none", choices=["none", "box", "outline"])
    parser.add_argument("text")

    args = parser.parse_args()
    print(args)

    style = Style()

    if args.style == "box":
        style = BoxStyle()
        args.bold = True
        args.italic = True
        args.stroke_width = 5

    if args.style == "outline":
        style = OutlineStyle()
        args.bold = True
        args.italic = True

    if not args.layer:
        if args.back_silk:
            args.layer = "B.SilkS"
        elif args.front_copper:
            args.layer = "F.Cu"
        elif args.back_copper:
            args.layer = "B.Cu"
        else:
            args.layer = "F.SilkS"

    arg_str = " ".join([shlex.quote(x) for x in sys.argv[1:]])

    mod_text = generate(
        text=args.text,
        layer=args.layer,
        size=args.size,
        font=args.font,
        bold=args.bold,
        italic=args.italic,
        stroke_width=args.stroke_width,
        align=args.align,
        line_spacing=args.line_spacing,
        dpi=args.dpi,
        style=style,
        comment=arg_str,
    )

    pyperclip.copy(mod_text)

    print("Copied to clipboard!")


if __name__ == "__main__":
    main()
