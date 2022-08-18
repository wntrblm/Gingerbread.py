# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import datetime
import io
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
    return S(ordinal, canonical_name, type, user_name)


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
    comments = (S("comment", n, comment) for n, comment in enumerate(comments))
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
    return S("fill", S("solid") if fill else "none")


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


def gr_text(
    text: str,
    *,
    at: S = at(0, 0),
    layer: str | S = layer("F.Cu"),
):
    layer = _layer_or_str(layer)

    return S(
        "gr_text",
        text,
        at,
        layer,
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
    pts: S,
    layer: str | S = layer("F.Cu"),
    width: float = 0.127,
    fill: bool = False,
):
    layer = _layer_or_str(layer)

    return S(
        "fp_poly",
        pts,
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
    suppress_zeros: bool = True,
):
    return S(
        "format",
        optional("prefix", prefix),
        optional("suffix", suffix),
        S("units", units),
        S("units_format", units_format),
        S("precision", precision),
        optional("override_value", override_value),
        optional("suppress_zeros", suppress_zeros),
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
    layer: str | S = layer("F.Cu"),
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
        S("type", type),
        layer,
        tstamp(),
        pts(S("xy", *start), S("xy", *end)),
        optional("height", height),
        optional("orientation", orientation),
        optional("leader_length", leader_length),
        optional("gr_text", gr_text),
        optional("format", format),
        style,
    )


# print(
#     kicad_pcb(
#         general(thickness=1.6),
#         paper(size="USLetter"),
#         title_block(title="Example Board"),
#         layers(
#             layer_def(0, "F.Cu", "signal"),
#             layer_def(31, "B.Cu", "signal"),
#             layer_def(32, "B.Adhes", "user", "B.Adhesive"),
#             layer_def(33, "F.Adhes", "user", "F.Adhesive"),
#             layer_def(34, "B.Paste", "user"),
#             layer_def(35, "F.Paste", "user"),
#             layer_def(36, "B.SilkS", "user", "B.Silkscreen"),
#             layer_def(37, "F.SilkS", "user", "F.Silkscreen"),
#             layer_def(38, "B.Mask", "user"),
#             layer_def(39, "F.Mask", "user"),
#             layer_def(40, "Dwgs.User", "user", "User.Drawings"),
#             layer_def(41, "Cmts.User", "user", "User.Comments"),
#             layer_def(42, "Eco1.User", "user", "User.Eco1"),
#             layer_def(43, "Eco2.User", "user", "User.Eco2"),
#             layer_def(44, "Edge.Cuts", "user"),
#             layer_def(45, "Margin", "user"),
#             layer_def(46, "B.CrtYd", "user", "B.Courtyard"),
#             layer_def(47, "F.CrtYd", "user", "F.Courtyard"),
#             layer_def(48, "B.Fab", "user"),
#             layer_def(49, "F.Fab", "user"),
#         ),
#         setup(),
#         net(0, ""),
#         gr_text(text="Test"),
#     )
# )
