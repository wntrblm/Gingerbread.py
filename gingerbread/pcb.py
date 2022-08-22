# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

"""PCB definition utilities"""

import datetime
import io
from os import PathLike

from . import _sexpr as s


class PCB:
    """A "builder" class for KiCAD PCBs"""

    # US Letter
    page_width = 279.4
    page_height = 215.9

    def __init__(
        self,
        title: str,
        rev: str = "v1",
        date: str = datetime.date.today().strftime("%Y-%m-%d"),
        company: str = "",
        comment1: str = "",
        comment2: str = "",
        comment3: str = "",
        comment4: str = "",
    ):
        self._finished = False
        self.offset = (0, 0)
        self.text = io.StringIO()
        self.title = title
        self.rev = rev
        self.date = date
        self.company = company
        self.comment1 = comment1
        self.comment2 = comment2
        self.comment3 = comment3
        self.comment4 = comment4
        self.bbox = (0, 0, 0, 0)
        self.items = []

    def add_line(self, x1, y1, x2, y2, *, layer: str = "F.SilkS", width: float = 0.1):
        self.items.append(
            s.gr_line(
                start=(x1 + self.offset[0], y1 + self.offset[1]),
                end=(x2 + self.offset[0], y2 + self.offset[1]),
                layer=layer,
                width=width,
            )
        )

    def add_poly(
        self,
        points: list[tuple[float, float]],
        *,
        layer: str = "F.SilkS",
        fill: bool = False,
        width: float = 0.1,
    ):
        pts = ((x + self.offset[0], y + self.offset[1]) for (x, y) in points)
        self.items.append(
            s.gr_poly(
                pts=pts,
                layer=layer,
                width=width,
                fill=fill,
            )
        )

    def add_rect(
        self,
        x,
        y,
        w,
        h,
        *,
        layer: str = "F.SilkS",
        width: float = 0.1,
        fill: bool = True,
    ):
        self.items.append(
            s.gr_rect(
                start=(x + self.offset[0], y + self.offset[1]),
                end=(x + w + self.offset[0], y + h + self.offset[1]),
                layer=layer,
                width=width,
                fill=fill,
            )
        )

    def add_drill(self, x, y, d):
        self.items.append(
            s.footprint(
                "DrillHole",
                s.pad(
                    "",
                    type="np_thru_hole",
                    shape="circle",
                    size=(d, d),
                    drill=s.drill(d),
                    layers="*.Cu *.Mask",
                    clearance=0.1,
                    zone_connect=0,
                ),
                at=(self.offset[0] + x, self.offset[1] + y),
            )
        )

    def add_slotted_hole(self, x: float, y: float, hole_size: float, slot_size: float):
        self.items.append(
            s.footprint(
                "DrillSlottedHole",
                s.pad(
                    "",
                    type="np_thru_hole",
                    shape="roundrect",
                    size=(hole_size, slot_size),
                    drill=s.drill(oval=True, diameter=hole_size, width=slot_size),
                    layers="*.Cu *.Mask",
                    roundrect_rratio=0.5,
                    clearance=0.1,
                    zone_connect=0,
                ),
                at=(self.offset[0] + x, self.offset[1] + y),
            )
        )

    def add_horizontal_measurement(
        self,
        x1,
        y1,
        x2,
        y2,
        text_size=1.27,
        text_thickness=0.15,
        below=False,
    ):
        x1 += self.offset[0]
        y1 += self.offset[1]
        x2 += self.offset[0]
        y2 += self.offset[1]
        height = 3 if below else -3
        value = round(x2 - x1, 2)

        self.items.append(
            s.dimension(
                start=(x1, y1),
                end=(x2, y2),
                type="aligned",
                height=height,
                locked=True,
                gr_text=s.gr_text(
                    f"{value:.2f} mm",
                    at=(x1, y1 + height / 2),
                    layer="Dwgs.User",
                    effects=s.effects(
                        size=(text_size, text_size),
                        thickness=text_thickness,
                    ),
                ),
                format=s.format(
                    units=2,
                    units_format=1,
                    precision=2,
                    suppress_zeroes=True,
                ),
                style=s.style(
                    thickness=text_thickness,
                    keep_text_aligned=True,
                ),
            )
        )

    def add_vertical_measurement(
        self,
        x1,
        y1,
        x2,
        y2,
        text_size=1.27,
        text_thickness=0.15,
        right=False,
    ):
        x1 += self.offset[0]
        y1 += self.offset[1]
        x2 += self.offset[0]
        y2 += self.offset[1]
        value = round(y2 - y1, 2)
        height = -3 if right else 3

        self.items.append(
            s.dimension(
                start=(x1, y1),
                end=(x2, y2),
                type="aligned",
                height=height,
                locked=True,
                gr_text=s.gr_text(
                    f"{value:.2f} mm",
                    at=(x1, y1 + height / 2),
                    layer="Dwgs.User",
                    effects=s.effects(
                        size=(text_size, text_size),
                        thickness=text_thickness,
                    ),
                ),
                format=s.format(
                    units=2,
                    units_format=1,
                    precision=2,
                ),
                style=s.style(
                    thickness=text_thickness,
                    keep_text_aligned=True,
                ),
            )
        )

    def add_literal(self, val: str):
        self.items.append(s.L(val))

    def write(self, filename_or_io):
        pcb = s.kicad_pcb(
            s.general(thickness=1.6),
            s.paper(size="USLetter"),
            s.title_block(
                title=self.title,
                company=self.company,
                comments=[self.comment1, self.comment2, self.comment3, self.comment4],
            ),
            s.layers(
                s.layer_def(0, "F.Cu", "signal"),
                s.layer_def(31, "B.Cu", "signal"),
                s.layer_def(32, "B.Adhes", "user", "B.Adhesive"),
                s.layer_def(33, "F.Adhes", "user", "F.Adhesive"),
                s.layer_def(34, "B.Paste", "user"),
                s.layer_def(35, "F.Paste", "user"),
                s.layer_def(36, "B.SilkS", "user", "B.Silkscreen"),
                s.layer_def(37, "F.SilkS", "user", "F.Silkscreen"),
                s.layer_def(38, "B.Mask", "user"),
                s.layer_def(39, "F.Mask", "user"),
                s.layer_def(40, "Dwgs.User", "user", "User.Drawings"),
                s.layer_def(41, "Cmts.User", "user", "User.Comments"),
                s.layer_def(42, "Eco1.User", "user", "User.Eco1"),
                s.layer_def(43, "Eco2.User", "user", "User.Eco2"),
                s.layer_def(44, "Edge.Cuts", "user"),
                s.layer_def(45, "Margin", "user"),
                s.layer_def(46, "B.CrtYd", "user", "B.Courtyard"),
                s.layer_def(47, "F.CrtYd", "user", "F.Courtyard"),
                s.layer_def(48, "B.Fab", "user"),
                s.layer_def(49, "F.Fab", "user"),
            ),
            s.setup(grid_origin=self.offset),
            s.net(0, ""),
            *self.items,
        )

        if isinstance(filename_or_io, (str, PathLike)):
            with open(filename_or_io, "w") as fh:
                pcb.write(fh)

        else:
            pcb.write(filename_or_io)
