# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

"""KiCAD S-Expression utility library

Note: KiCAD's S-Expression parser *is* position sensitive, so care must be taken with re-ordering items.
"""

import datetime
import io
import uuid as _uuid
from typing import Union

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


class Literal:
    def __init__(self, val):
        self.val = val


L = Literal


class Symbol:
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


S = Symbol


def _opt(name: str, val, *args) -> S | None:
    if val is False or val is None:
        return None
    elif val is True:
        return S(name, *args)
    else:
        return S(name, val, *args)


def width(width: float):
    return S("width", width)


def at(x: Union[S, float] = 0, y: float = 0, angle: float = None):
    if isinstance(x, S):
        return x
    return S("at", x, y, angle)


def xy(x: float, y: float):
    return S("xy", x, y)


def pts(*pts: list[Union[S, tuple[float, float]]]):
    if not pts:
        return None
    if isinstance(pts[0], S) and pts[0].token == "pts":
        return pts[0]

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
        _opt("solder_mask_min_width", solder_mask_min_width),
        _opt("pad_to_paste_clearance", pad_to_paste_clearance),
        _opt("pad_to_paste_clearance_ratio", pad_to_paste_clearance_ratio),
        _opt("pad_to_paste_clearance_ratio", pad_to_paste_clearance_ratio),
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
    return S("paper", size, width, height, _opt("portrait", portrait))


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
        _opt("type", type),
        _opt("board_only", board_only),
        _opt("exclude_from_pos_files", exclude_from_pos_files),
        _opt("exclude_from_bom", exclude_from_bom),
    )


def footprint(
    library_link: str,
    *args,
    locked: bool = False,
    layer: str | S = layer("F.Cu"),
    at: tuple[float, float] = (0, 0),
    attr: S = attr(),
):
    layer = _layer_or_str(layer)

    return S(
        "footprint",
        library_link,
        _opt("locked", locked),
        layer,
        globals()["at"](*at),
        attr,
        tstamp(),
        tedit(),
        *args,
    )


def fp_text(
    text: str,
    *,
    at: tuple[float, float] = (0, 0),
    type: str = "user",
    layer: str | S = layer("F.Cu"),
    hide: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_text",
        S(type),
        text,
        globals()["at"](*at),
        layer,
        _opt("hide", hide),
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
        _opt("locked", locked),
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
        _opt("locked", locked),
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
        _opt("locked", locked),
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
        _opt("locked", locked),
        tstamp(),
    )


def fp_poly(
    *,
    pts: list[tuple[float, float]],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_poly",
        globals()["pts"](*pts),
        layer,
        globals()["width"](width),
        globals()["fill"](fill),
        _opt("locked", locked),
        tstamp(),
    )


def fp_curve(
    *,
    pts: list[tuple[float, float]],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    locked: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_curve",
        globals()["pts"](*pts),
        layer,
        globals()["width"](width),
        _opt("locked", locked),
        tstamp(),
    )


def pad(
    number: str,
    *,
    type: str,
    shape: str,
    layers: str,
    at: tuple[float, float] = (0, 0),
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
        globals()["at"](*at),
        _opt("locked", locked),
        S("size", *size),
        drill,
        S("layers", S(layers)),
        _opt("roundrect_rratio", roundrect_rratio),
        _opt("chamfer_ratio", chamfer_ratio),
        chamfer,
        net,
        _opt("pinfunction", pinfunction),
        _opt("pintype", pintype),
        _opt("zone_connect", zone_connect),
        _opt("clearance", clearance),
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

    return S("drill", _opt("oval", oval), diameter, width, _opt("offset", offset))


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
        _opt("left", left),
        _opt("right", right),
        _opt("top", top),
        _opt("bottom", bottom),
        _opt("mirror", mirror),
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
            _opt("thickness", thickness),
            _opt("bold", bold),
            _opt("italic", italic),
        ),
        justify,
    )


def gr_text(
    text: str,
    *,
    at: tuple[float, float] = (0, 0),
    layer: str | S = layer("F.Cu"),
    effects: S = None,
):
    layer = _layer_or_str(layer)

    return S(
        "gr_text",
        text,
        globals()["at"](*at),
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
    pts: list[float, float],
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
    pts: list[float, float],
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
):
    layer = _layer_or_str(layer)

    return S(
        "gr_curve",
        globals()["pts"](*pts),
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
        _opt("prefix", prefix),
        _opt("suffix", suffix),
        S("units", units),
        S("units_format", units_format),
        S("precision", precision),
        _opt("override_value", override_value),
        _opt("suppress_zeroes", suppress_zeroes),
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
        _opt("extension_height", extension_height),
        _opt("text_frame", text_frame),
        _opt("extension_offset", extension_offset),
        _opt("keep_text_aligned", keep_text_aligned),
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
        _opt("locked", locked),
        S("type", S(type)),
        layer,
        tstamp(),
        pts(S("xy", *start), S("xy", *end)),
        _opt("height", height),
        _opt("orientation", orientation),
        _opt("leader_length", leader_length),
        gr_text,
        format,
        style,
    )
