# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

"""Fancytext generates beautiful text labels for KiCAD"""

# References:
# - https://github.com/leifgehrmann/pangocffi/tree/master/tests/functional
# - https://pangocairocffi.readthedocs.io/en/latest/tests.html
# - https://pangocairocffi.readthedocs.io/en/latest/
# - https://pangocffi.readthedocs.io/en/latest/modules.html#text-attribute-markup
# - https://github.com/leifgehrmann/pangocairocffi/blob/master/tests/test_extents.py
# - https://gitlab.gnome.org/GNOME/librsvg/-/blob/main/src/text.rs#L1219w
# - https://docs.gtk.org/Pango/
# - https://gist.github.com/ynkdir/849071

import argparse
import html
import math
import pathlib
import sys
from cmath import sqrt

import rich
import tinycss2.color3

from . import trace
from ._cffi_deps import cairocffi, pangocairocffi, pangocffi
from ._print import printv, set_verbose
from ._utils import default_param_value


def get_context_size(context: cairocffi.Context) -> tuple[int, int]:
    target = context.get_target()
    return (target.get_width(), target.get_height())


class Text:
    def __init__(
        self,
        *,
        text,
        font,
        bold=False,
        italic=False,
        strikethrough=False,
        underline=False,
        overline=False,
        size_mm=2,
        line_spacing=1,
        align="center",
        fill="black",
        stroke="black",
        stroke_width_mm=0,
        dpmm=100,
    ):
        self.text = text
        self.size_mm = size_mm
        self.bold = bold
        self.italic = italic
        self.strikethrough = strikethrough
        self.underline = underline
        self.overline = overline
        self.line_spacing = line_spacing
        self.font = font
        self.align = align
        self.fill = tinycss2.color3.parse_color(fill)
        self.stroke = tinycss2.color3.parse_color(stroke)
        self.stroke_width_mm = stroke_width_mm
        self.dpmm = dpmm

        self._init_layout()

    def _markup(self):
        size_px = self.size_mm * self.dpmm
        bold = "bold" if self.bold else ""
        italic = "italic" if self.italic else ""
        strikethrough = 'strikethrough="true"' if self.strikethrough else ""
        underline = 'underline="single"' if self.underline else ""

        return (
            f"<span "
            f'font="{self.font} {bold} {italic} {size_px}px" '
            f"{strikethrough} {underline}"
            f'line_height="{self.line_spacing}">'
            f"{html.escape(self.text)}"
            f"</span>"
        )

    def _init_layout(self):
        self._surface = cairocffi.RecordingSurface(cairocffi.CONTENT_COLOR_ALPHA, None)
        self._cairo = cairocffi.Context(self._surface)
        self._layout = pangocairocffi.create_layout(self._cairo)

        self._layout.set_alignment(getattr(pangocffi.Alignment, self.align.upper()))
        self._layout.set_width(-1)
        self._layout.set_markup(self._markup())

        self.baseline_px = pangocffi.units_to_double(self._layout.get_baseline())

        ink, logical = self._layout.get_extents()
        self.ink_extents_px = [
            pangocffi.units_to_double(ink.x),
            pangocffi.units_to_double(ink.y),
            pangocffi.units_to_double(ink.width),
            pangocffi.units_to_double(ink.height),
        ]
        self.ink_extents_mm = [u / self.dpmm for u in self.ink_extents_px]
        self.logical_extents_px = [
            pangocffi.units_to_double(logical.x),
            pangocffi.units_to_double(logical.y),
            pangocffi.units_to_double(logical.width),
            pangocffi.units_to_double(logical.height),
        ]
        self.logical_extents_mm = [u / self.dpmm for u in self.logical_extents_px]

    def absolute_extents_px(self, context):
        surface_w_px, surface_h_px = get_context_size(context)
        w, h = self.ink_extents_px[2:]

        return (surface_w_px / 2 - w / 2, surface_h_px / 2 - h / 2, w, h)

    def _draw_overbar(self, context: cairocffi.Context):
        # Pango's default overbar doesn't look great (it's too high up), so
        # this re-implements to more closely match what KiCAD does.

        # Get the underline thickness info from the font. This is a little involved because
        # pangocffi doesn't wrap the methods we need.
        desc = pangocffi.FontDescription()
        desc.set_family(self.font)
        desc.set_weight(pangocffi.Weight.BOLD if self.bold else pangocffi.Weight.NORMAL)
        desc.set_size(pangocffi.units_from_double(self.size_mm * self.dpmm))
        metrics = pangocffi.pango.pango_context_get_metrics(
            self._layout.get_context()._pointer, desc._pointer, pangocffi.ffi.NULL
        )
        underline_thickness_px = pangocffi.units_to_double(
            pangocffi.pango.pango_font_metrics_get_underline_thickness(metrics)
        )
        pangocffi.pango.pango_font_metrics_unref(metrics)

        # Now that we know the underline thickness, we cna use that to draw the overbar.
        context.save()
        context.set_line_width(
            underline_thickness_px + (self.stroke_width_mm * self.dpmm)
        )
        context.new_path()
        context.move_to(0, 0)
        context.line_to(self.ink_extents_px[2], 0)
        context.stroke()
        context.restore()

    def draw(self, context: cairocffi.Context):
        context.save()

        x, y, w, h = self.absolute_extents_px(context)
        printv(f"Ink extents: {x=} {y=} {w=} {h=}")
        y = y - self.ink_extents_px[1]

        context.translate(x, y)

        pangocairocffi.layout_path(context, self._layout)

        context.set_source_rgba(*self.fill)
        context.fill_preserve()

        stroke_width_px = self.stroke_width_mm * self.dpmm

        context.set_source_rgba(*self.stroke)
        context.set_line_width(stroke_width_px)
        context.set_line_cap(cairocffi.LINE_CAP_ROUND)
        context.set_line_join(cairocffi.LINE_JOIN_ROUND)
        context.stroke()

        if self.overline:
            self._draw_overbar(context)

        context.restore()


class Outline:
    def __init__(
        self,
        left="(",
        right=")",
        fill="black",
        stroke="black",
        stroke_width_mm=0.1,
        padding_mm=(1, 1),
    ):
        self.left = left
        self.right = right
        self.fill = tinycss2.color3.parse_color(fill)
        self.stroke = tinycss2.color3.parse_color(stroke)
        self.stroke_width_mm = stroke_width_mm
        self.padding_mm = padding_mm

    def preprocess(self, text: str):
        if text.startswith(("|", "[", "(", "<", "/", "\\")):
            self.left = text[0]
            text = text[1:]
        if text.endswith(("|", "]", ")", ">", "/", "\\")):
            self.right = text[-1]
            text = text[0:-1]
        return text

    def draw(self, context: cairocffi.Context, text: Text):
        t_x, t_y, t_w, t_h = text.absolute_extents_px(context)
        pad_x = self.padding_mm[0] * text.dpmm
        pad_y = self.padding_mm[1] * text.dpmm
        pad_x_h = pad_x / 2
        x = t_x - pad_x_h
        y = t_y - pad_y / 2
        w = t_w + pad_x
        h = t_h + pad_y
        h_hyp = h / sqrt(2).real
        stroke_width_px = self.stroke_width_mm * text.dpmm

        context.save()
        context.translate(x, y)

        match self.left:
            case "|":
                context.move_to(0, 0)
                context.line_to(0, h)
                context.line_to(w / 2, h)
                context.line_to(w / 2, 0)
                context.line_to(0, 0)
            case "[":
                context.move_to(-h_hyp / 2, 0)
                context.line_to(-h_hyp / 2, h)
                context.line_to(w / 2, h)
                context.line_to(w / 2, 0)
                context.line_to(-h_hyp / 2, 0)
            case "/":
                context.move_to(0, 0)
                context.line_to(-h_hyp, h)
                context.line_to(w / 2, h)
                context.line_to(w / 2, 0)
                context.line_to(0, 0)
            case "\\":
                context.move_to(-h_hyp, 0)
                context.line_to(0, h)
                context.line_to(w / 2, h)
                context.line_to(w / 2, 0)
                context.line_to(-h_hyp, 0)
            case "<":
                context.move_to(0, 0)
                context.line_to(-h_hyp, h / 2)
                context.line_to(0, h)
                context.line_to(w / 2, h)
                context.line_to(w / 2, 0)
                context.line_to(0, 0)
            case "(":
                context.move_to(0, h)
                context.arc(0, h / 2, h / 2, math.radians(90), math.radians(270))
                context.line_to(w / 2, 0)
                context.line_to(w / 2, h)
                context.line_to(0, h)

        match self.right:
            case "|":
                context.move_to(w / 2, 0)
                context.line_to(w / 2, h)
                context.line_to(w, h)
                context.line_to(w, 0)
                context.line_to(w / 2, 0)
            case "]":
                context.move_to(w / 2, 0)
                context.line_to(w / 2, h)
                context.line_to(w + h_hyp / 2, h)
                context.line_to(w + h_hyp / 2, 0)
                context.line_to(w / 2, 0)
            case "/":
                context.move_to(w / 2, 0)
                context.line_to(w / 2, h)
                context.line_to(w, h)
                context.line_to(w + h_hyp, 0)
                context.line_to(w / 2, 0)
            case "\\":
                context.move_to(w / 2, 0)
                context.line_to(w / 2, h)
                context.line_to(w + h_hyp, h)
                context.line_to(w, 0)
                context.line_to(w / 2, 0)
            case ">":
                context.move_to(w / 2, 0)
                context.line_to(w / 2, h)
                context.line_to(w, h)
                context.line_to(w + h_hyp, h / 2)
                context.line_to(w, 0)
                context.line_to(w / 2, 0)
            case ")":
                context.move_to(w / 2, 0)
                context.arc(w, h / 2, h / 2, math.radians(-90), math.radians(90))
                context.line_to(w / 2, h)
                context.line_to(w / 2, 0)

        context.set_line_width(stroke_width_px)
        context.set_line_cap(cairocffi.LINE_CAP_ROUND)
        context.set_line_join(cairocffi.LINE_JOIN_ROUND)
        context.set_source_rgba(*self.stroke)
        context.stroke_preserve()
        context.set_source_rgba(*self.fill)
        context.fill()

        context.restore()


def generate(
    *,
    text,
    font="Space Mono",
    bold=False,
    italic=False,
    strikethrough=False,
    underline=False,
    overline=False,
    layer="F.SilkS",
    size_mm=2,
    stroke_mm=0,
    align="center",
    line_spacing=1,
    padding_mm=[1, 1],
    dpi=2540,
    outline_stroke_mm=0,
    outline_fill=False,
    position=(0, 0),
):
    dpmm = dpi / 25.4
    flip = layer.startswith("B.")

    outline_ = Outline(
        fill="black" if outline_fill else "white",
        stroke_width_mm=outline_stroke_mm,
        padding_mm=padding_mm,
    )

    text = outline_.preprocess(text)

    text_ = Text(
        text=text,
        font=font,
        bold=bold,
        italic=italic,
        strikethrough=strikethrough,
        underline=underline,
        overline=overline,
        size_mm=size_mm,
        fill="white" if outline_fill else "black",
        stroke_width_mm=stroke_mm,
        stroke="white" if outline_fill else "black",
        line_spacing=line_spacing,
        align=align,
    )

    w_px = round(text_.ink_extents_px[2] + (padding_mm[0] + 30) * dpmm)
    h_px = round(text_.ink_extents_px[3] + (padding_mm[1] + 10) * dpmm)
    printv(f"Surface size {w_px=} {h_px=}")

    surface = cairocffi.ImageSurface(cairocffi.FORMAT_ARGB32, w_px, h_px)
    context = cairocffi.Context(surface)

    context.rectangle(0, 0, w_px, h_px)
    context.set_source_rgb(1, 1, 1)
    context.fill()

    if flip:
        printv("Outputting on back layer, flipping image")
        context.scale(-1, 1)
        context.translate(-w_px, 0)

    if outline_stroke_mm:
        outline_.draw(context, text_)

    text_.draw(context)

    printv("Tracing image")
    fp = trace.trace(
        surface,
        invert=False,
        threshold=127,
        dpi=dpi,
        layer=layer,
        center=True,
        position=position,
    )

    return fp


def main():
    import pyperclip

    parser = argparse.ArgumentParser(
        "fancytext", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable to print additional information during generation",
    )

    g = parser.add_argument_group(title="text")
    g.add_argument(
        "--font", default=default_param_value(generate, "font"), help="Font family name"
    )
    g.add_argument("--bold", action=argparse.BooleanOptionalAction)
    g.add_argument("--italic", action=argparse.BooleanOptionalAction)
    g.add_argument("--strikethrough", action=argparse.BooleanOptionalAction)
    g.add_argument("--underline", action=argparse.BooleanOptionalAction)
    g.add_argument("--overline", action=argparse.BooleanOptionalAction)
    g.add_argument(
        "--size",
        type=float,
        default=default_param_value(generate, "size_mm"),
        help="Text height, in mm",
    )
    g.add_argument(
        "--stroke",
        type=float,
        default=default_param_value(generate, "stroke_mm"),
        help="Additional outline stroke to add to the text, in mm",
    )
    g.add_argument(
        "--line-spacing",
        type=float,
        default=default_param_value(generate, "line_spacing"),
        help="Spacing between lines in multiples of the font's line height",
    )

    g.add_argument(
        "--align",
        default="center",
        choices=["left", "center", "right"],
        help="Text alignment",
    )

    g = parser.add_argument_group(title="outline")
    g.add_argument(
        "--padding",
        type=float,
        nargs=2,
        default=default_param_value(generate, "padding_mm"),
        help="Amount of padding between the outline box and the text, in mm",
    )
    g.add_argument(
        "--outline-stroke",
        type=float,
        default=default_param_value(generate, "outline_stroke_mm"),
        help="Outline stroke thickness, in mm",
    )
    g.add_argument(
        "--outline-fill",
        action=argparse.BooleanOptionalAction,
        default=default_param_value(generate, "outline_fill"),
        help="Whether or not the outline box is filled",
    )

    g = parser.add_argument_group(title="output")
    mg = g.add_mutually_exclusive_group()
    mg.add_argument("--layer", default=None)
    mg.add_argument("--front-silk", action="store_true")
    mg.add_argument("--back-silk", action="store_true")
    mg.add_argument("--front-copper", action="store_true")
    mg.add_argument("--back-copper", action="store_true")

    g.add_argument(
        "--dpi",
        type=int,
        default=default_param_value(generate, "dpi"),
        help="Dots per inch, higher values result in better resolution but longer processing time",
    )

    parser.add_argument("text")
    args = parser.parse_args()

    set_verbose(args.verbose)

    if args.back_silk:
        args.layer = "B.SilkS"
    elif args.front_copper:
        args.layer = "F.Cu"
    elif args.back_copper:
        args.layer = "B.Cu"
    elif args.front_silk:
        args.layer = "F.SilkS"
    elif not args.layer:
        args.layer = "F.SilkS"

    mod_text = generate(
        text=args.text,
        font=args.font,
        bold=args.bold,
        italic=args.italic,
        strikethrough=args.strikethrough,
        underline=args.underline,
        overline=args.overline,
        size_mm=args.size,
        stroke_mm=args.stroke,
        line_spacing=args.line_spacing,
        align=args.align,
        layer=args.layer,
        dpi=args.dpi,
        padding_mm=args.padding,
        outline_stroke_mm=args.outline_stroke,
        outline_fill=args.outline_fill,
    )

    try:
        pyperclip.copy(mod_text)
        rich.print("[green]Copied to clipboard! :purple_heart:", file=sys.stderr)
    except pyperclip.PyperclipException:
        rich.print("[yellow]Unable to copy to clipboard, saving as fancytext.kicad_mod")
        pathlib.Path("fancytext.kicad_mod").write_text(mod_text)


if __name__ == "__main__":
    main()
