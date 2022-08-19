# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import datetime
import io
from typing import Iterable
import uuid as _uuid

# https://dev-docs.kicad.org/en/file-formats/sexpr-intro/


def escape_string(s, out: io.TextIOBase):
    # Based on https://docs.kicad.org/doxygen/string__utils_8cpp.html#ada40aaecc8d7b17fa613cf02bf4da7fb
    out.write('"')
    for c in s:
        match s:
            case "\n":
                out.write("\\n")
            case "\r":
                out.write("\\r")
            case "{":
                out.write("{brace}")
            case "/":
                out.write("{slash}")
            case "\\":
                out.write("{backlash}")
            case "<":
                out.write("{lt}")
            case ">":
                out.write("{gt}")
            case ":":
                out.write("{colon}")
            case '"':
                out.write("{dblqoute}")
            case _:
                out.write(c)
    out.write('"')


class Literal():
    def __init__(self, val):
        self.val = val

literal = Literal

class S:
    def __init__(self, token, *attributes):
        self.token = token
        self.attributes = [x for x in attributes if x is not None]

    def write(self, out: io.TextIOBase, depth=0):

        tabbed = False
        tab = "  " * depth
        if depth:
            out.write("\n")
            out.write(tab)

        if not self.attributes:
            out.write(self.token)
            return

        out.write(f"({self.token}")

        for attr in self.attributes:
            match attr:
                case Literal():
                    out.write(attr.val)
                case S():
                    if attr.attributes:
                        tabbed = True
                        attr.write(out, depth=depth + 1)
                    else:
                        out.write(" ")
                        attr.write(out)
                case str():
                    out.write(" ")
                    escape_string(attr, out)
                case float():
                    out.write(f" {attr:0.6f}")
                case _uuid.UUID():
                    out.write(" ")
                    escape_string(str(attr), out)
                case _:
                    out.write(f" {attr}")

        if not tabbed:
            out.write(")")
        else:
            out.write(f"\n{tab})")

    def __repr__(self) -> str:
        out = io.StringIO()
        self.write(out)
        return out.getvalue()

    def __str__(self) -> str:
        return self.__repr__()


def optional(name: str, val, *args) -> S | None:
    if val is False or val is None:
        return None
    elif val is True:
        return S(name, *args)
    else:
        return S(name, val, *args)


def width(width: float):
    return S("width", width)


def at(x: float, y: float, *, angle: float = None):
    return S("at", x, y, angle)


def xy(x: float, y: float):
    return S("xy", x, y)


def pts(*pts: list[S]):
    pts = (pt if isinstance(pt, S) else xy(*pt) for pt in pts)
    return S("pts", *pts)


def kicad_pcb(
    *args,
    version: int = 20211014,
    generator: str = "Gingerbread",
):
    return S(
        "kicad_pcb",
        S("version", version),
        S("generator", generator),
        *args,
    )


def general(*, thickness: float = 1.6):
    return S("general", S("thickness", thickness))


def layer_def(ordinal: int, canonical_name: str, type: str, user_name: str = None):
    return S(ordinal, canonical_name, S(type), user_name)


def layers(*defs: list[S]):
    return S("layers", *defs)


def setup(
    *plot_settings,
    pad_to_mask_clearance: float = 0,
    stackup: S = None,
    solder_mask_min_width: float = None,
    pad_to_paste_clearance: float = None,
    pad_to_paste_clearance_ratio: float = None,
    aux_axis_origin: tuple[float, float] = None,
    grid_origin: tuple[float, float] = None,
):
    if aux_axis_origin is not None:
        aux_axis_origin = S("aux_axis_origin", *aux_axis_origin)

    if grid_origin is not None:
        grid_origin = S("grid_origin", *grid_origin)

    return S(
        "setup",
        stackup,
        S("pad_to_mask_clearance", pad_to_mask_clearance),
        optional("solder_mask_min_width", solder_mask_min_width),
        optional("pad_to_paste_clearance", pad_to_paste_clearance),
        optional("pad_to_paste_clearance_ratio", pad_to_paste_clearance_ratio),
        optional("pad_to_paste_clearance_ratio", pad_to_paste_clearance_ratio),
        aux_axis_origin,
        grid_origin,
        *plot_settings,
    )


def paper(
    *,
    size: str = None,
    width: float = None,
    height: float = None,
    portrait: bool = False,
):
    return S("paper", size, width, height, optional("portrait", portrait))


def title_block(
    *,
    title: str,
    date: datetime.date = datetime.date.today(),
    rev: str = "",
    company: str = "",
    comments: list[str] = [],
):
    comments = (S("comment", n, comment) for n, comment in enumerate(comments, 1))
    return S(
        "title_block",
        S("title", title),
        S("date", date.strftime("%Y%m%d")),
        S("rev", rev),
        S("company", company),
        *comments,
    )


def net(ordinal, name):
    return S("net", ordinal, name)


def uuid(val: _uuid.UUID = None):
    if val is None:
        val = _uuid.uuid1()
    return S("uuid", val)


def tstamp(val: _uuid.UUID = None):
    if val is None:
        val = _uuid.uuid1()
    return S("tstamp", val)


def tedit(val: _uuid.UUID = None):
    if val is None:
        val = _uuid.uuid1()
    return S("tedit", val)


def layer(*defs: list[str]):
    return S("layer", *defs)


def _layer_or_str(v):
    if isinstance(v, S):
        return v
    return S("layer", v)


def attr(
    *,
    type: str = None,
    board_only: bool = True,
    exclude_from_pos_files: bool = True,
    exclude_from_bom: bool = True,
):
    return S(
        "attr",
        optional("type", type),
        optional("board_only", board_only),
        optional("exclude_from_pos_files", exclude_from_pos_files),
        optional("exclude_from_bom", exclude_from_bom),
    )


def footprint(
    library_link: str,
    *args,
    locked: bool = False,
    layer: str | S = layer("F.Cu"),
    at: S = at(0, 0),
    attr: S = attr(),
):
    layer = _layer_or_str(layer)

    return S(
        "footprint",
        library_link,
        optional("locked", locked),
        layer,
        at,
        attr,
        tstamp(),
        tedit(),
        *args,
    )


def fp_text(
    text: str,
    *,
    at: S = at(0, 0),
    type: str = "user",
    layer: str | S = layer("F.Cu"),
    hide: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_text",
        S(type),
        text,
        at,
        layer,
        optional("hide", hide),
        tstamp(),
    )


def fp_line(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_line",
        S("start", *start),
        S("end", *end),
        layer,
        globals()["width"](width),
        optional("locked", locked),
        tstamp(),
    )


def fp_rect(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_rect",
        S("start", *start),
        S("end", *end),
        layer,
        globals()["width"](width),
        optional("locked", locked),
        globals()["fill"](fill),
        tstamp(),
    )


def fill(fill: bool):
    return S("fill", S("solid" if fill else "none"))


def fp_circle(
    *,
    center: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_circle",
        S("center", *center),
        S("end", *end),
        layer,
        globals()["width"](width),
        optional("locked", locked),
        globals()["fill"](fill),
        tstamp(),
    )


def fp_arc(
    *,
    start: tuple[float, float],
    mid: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_arc",
        S("start", *start),
        S("mid", *mid),
        S("end", *end),
        layer,
        globals()["width"](width),
        optional("locked", locked),
        tstamp(),
    )


def fp_poly(
    *,
    pts: S,
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_poly",
        pts,
        layer,
        globals()["width"](width),
        globals()["fill"](fill),
        optional("locked", locked),
        tstamp(),
    )


def fp_curve(
    *,
    pts: S,
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_curve",
        pts,
        layer,
        globals()["width"](width),
        optional("locked", locked),
        tstamp(),
    )


def pad(
    number: str,
    *,
    type: str,
    shape: str,
    layers: str,
    at: S = at(0, 0),
    size: tuple[float, float],
    locked: bool = False,
    drill: S = None,
    roundrect_rratio: float = None,
    chamfer_ratio: float = None,
    chamfer: tuple[float, float, float, float] = None,
    net: S = None,
    pinfunction: str = None,
    pintype: str = None,
    zone_connect: int = None,
    clearance: float = None,
):
    if chamfer is not None:
        chamfer = S("chamfer", *chamfer)

    return S(
        "pad",
        str(number),
        S(type),
        S(shape),
        at,
        optional("locked", locked),
        S("size", *size),
        drill,
        S("layers", S(layers)),
        optional("roundrect_rratio", roundrect_rratio),
        optional("chamfer_ratio", chamfer_ratio),
        chamfer,
        net,
        optional("pinfunction", pinfunction),
        optional("pintype", pintype),
        optional("zone_connect", zone_connect),
        optional("clearance", clearance),
        tstamp(),
    )


def drill(
    diameter: float,
    oval: bool = False,
    width: float = None,
    offset: tuple[float, float] = None,
):
    if offset is not None:
        offset = S("offset", *offset)

    return S(
        "drill", optional("oval", oval), diameter, width, optional("offset", offset)
    )


def justify(
    *,
    left: bool = None,
    right: bool = None,
    top: bool = None,
    bottom: bool = None,
    mirror: bool = None,
):
    return S(
        "justify",
        optional("left", left),
        optional("right", right),
        optional("top", top),
        optional("bottom", bottom),
        optional("mirror", mirror),
    )


def effects(
    *,
    size: tuple[float, float],
    thickness: float = None,
    bold: bool = None,
    italic: bool = None,
    justify: S = None,
):
    return S(
        "effects",
        S(
            "font",
            S("size", *size),
            optional("thickness", thickness),
            optional("bold", bold),
            optional("italic", italic),
        ),
        justify,
    )


def gr_text(
    text: str, *, at: S = at(0, 0), layer: str | S = layer("F.Cu"), effects: S = None
):
    layer = _layer_or_str(layer)

    return S(
        "gr_text",
        text,
        at,
        layer,
        effects,
        tstamp(),
    )


def gr_line(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
):
    layer = _layer_or_str(layer)

    return S(
        "gr_line",
        S("start", *start),
        S("end", *end),
        layer,
        globals()["width"](width),
        tstamp(),
    )


def gr_rect(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "gr_rect",
        S("start", *start),
        S("end", *end),
        layer,
        globals()["width"](width),
        globals()["fill"](fill),
        tstamp(),
    )


def gr_circle(
    *,
    center: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_circle",
        S("center", *center),
        S("end", *end),
        layer,
        globals()["width"](width),
        globals()["fill"](fill),
        tstamp(),
    )


def gr_arc(
    *,
    start: tuple[float, float],
    mid: tuple[float, float],
    end: tuple[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
):
    layer = _layer_or_str(layer)

    return S(
        "gr_arc",
        S("start", *start),
        S("mid", *mid),
        S("end", *end),
        layer,
        globals()["width"](width),
        tstamp(),
    )


def gr_poly(
    *,
    pts: Iterable,
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "gr_poly",
        globals()["pts"](*pts),
        layer,
        globals()["width"](width),
        globals()["fill"](fill),
        tstamp(),
    )


def gr_curve(
    *,
    pts: S,
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
):
    layer = _layer_or_str(layer)

    return S(
        "gr_curve",
        pts,
        layer,
        globals()["width"](width),
        tstamp(),
    )


def format(
    *,
    prefix: str = None,
    suffix: str = None,
    units: int = 3,
    units_format: int = 1,
    precision: int = 3,
    override_value: str = None,
    suppress_zeroes: bool = True,
):
    return S(
        "format",
        optional("prefix", prefix),
        optional("suffix", suffix),
        S("units", units),
        S("units_format", units_format),
        S("precision", precision),
        optional("override_value", override_value),
        optional("suppress_zeroes", suppress_zeroes),
    )


def style(
    *,
    thickness: float = 0.127,
    arrow_length: float = 1.27,
    text_position_mode: int = 0,
    extension_height: float = None,
    text_frame: int = None,
    extension_offset: float = None,
    keep_text_aligned: bool = None,
):
    return S(
        "style",
        S("thickness", thickness),
        S("arrow_length", arrow_length),
        S("text_position_mode", text_position_mode),
        optional("extension_height", extension_height),
        optional("text_frame", text_frame),
        optional("extension_offset", extension_offset),
        optional("keep_text_aligned", keep_text_aligned),
    )


def dimension(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    type: str = "aligned",
    layer: str | S = layer("Dwgs.User"),
    locked: bool = False,
    height: float = None,
    orientation: float = None,
    leader_length: float = None,
    gr_text: S = None,
    format: S = None,
    style: S = None,
):
    layer = _layer_or_str(layer)

    return S(
        "dimension",
        optional("locked", locked),
        S("type", S(type)),
        layer,
        tstamp(),
        pts(S("xy", *start), S("xy", *end)),
        optional("height", height),
        optional("orientation", orientation),
        optional("leader_length", leader_length),
        gr_text,
        format,
        style,
    )
