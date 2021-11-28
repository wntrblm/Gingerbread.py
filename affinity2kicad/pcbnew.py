# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import io
import math
import datetime


def _vector_length(x, y):
    return math.sqrt((x ** 2 + y ** 2))


class PCB:
    # US Letter
    page_width = 279.4
    page_height = 215.9

    def __init__(self, title, rev="v1"):
        self._finished = False
        self.offset = (0, 0)
        self.text = io.StringIO()
        self.title = title
        self.rev = rev
        self.date = datetime.date.today().isoformat().replace("-", "/")
        self.company = "Winterbloom"
        self.comment1 = "Alethea Flowers"
        self.comment2 = "CC BY-NC-ND 4.0"
        self.comment3 = ""
        self.comment4 = ""

    def start(
        self,
    ):
        self.text.write(
            _pcb_start_template(
                self.title,
                self.date,
                self.rev,
                self.company,
                self.comment1,
                self.comment2,
                self.comment3,
                self.comment4,
                self.offset[0],
                self.offset[1],
            )
        )

    def add_line(self, x1, y1, x2, y2):
        self.text.write(
            f"(gr_line (start {x1 + self.offset[0]} {y1 + self.offset[1]}) (end {x2 + self.offset[0]} {y2 + self.offset[1]}) (layer Edge.Cuts) (width 0.5))\n"
        )

    def add_arc(self, center_x, center_y, end_x, end_y, rotation):
        self.text.write(
            f"(gr_arc (start {center_x + self.offset[0]} {center_y + self.offset[1]}) (end {end_x + self.offset[0]} {end_y + self.offset[1]}) (angle {rotation}) (layer Edge.Cuts) (width 0.5))\n"
        )

    def add_outline(self, x, y, width, height):
        self.text.write(
            _outline_template(x + self.offset[0], y + self.offset[1], width, height)
        )

    def add_drill(self, x, y, d):
        self.text.write(_drill_template(x + self.offset[0], y + self.offset[1], d))

    def add_horizontal_measurement(
        self,
        x1,
        y1,
        x2,
        y2,
        crossbar_offset=3,
        arrow_span=0.6,
        arrow_length=1.1,
        text_size=1,
        text_thickness=0.15,
    ):
        width = x2 - x1
        height = y2 - y1
        length = round(_vector_length(width, height), 2)
        x1 += self.offset[0]
        y1 += self.offset[1]
        x2 += self.offset[0]
        y2 += self.offset[1]
        self.text.write(
            _horizontal_measurement_template(
                x1,
                y1,
                x2,
                y2,
                length,
                width,
                crossbar_offset,
                arrow_length,
                arrow_span,
                text_size,
                text_thickness,
            )
        )

    def add_vertical_measurement(
        self,
        x1,
        y1,
        x2,
        y2,
        crossbar_offset=-3,
        arrow_span=0.6,
        arrow_length=1.1,
        text_size=1,
        text_thickness=0.15,
    ):
        width = x2 - x1
        height = y2 - y1
        length = round(_vector_length(width, height), 2)
        x1 += self.offset[0]
        y1 += self.offset[1]
        x2 += self.offset[0]
        y2 += self.offset[1]
        self.text.write(
            _vertical_measurement_template(
                x1,
                y1,
                x2,
                y2,
                length,
                height,
                crossbar_offset,
                arrow_length,
                arrow_span,
                text_size,
                text_thickness,
            )
        )

    def add_mod(self, filename, x, y, orientation=0, relative=True):
        if relative:
            x += self.offset[0]
            y += self.offset[1]
        mod = open(filename, "r").read()
        mod = mod.replace("(at 0 0)", f"(at {x:.2f} {y:.2f} {orientation})", 1)
        self.text.write(mod)

    def add_slotted_hole(self, x, y, hole_size, slot_size):
        self.text.write(
            _slotted_hole_template(
                self.offset[0] + x, self.offset[1] + y, hole_size, slot_size
            )
        )

    def finish(self):
        if not self._finished:
            self.text.write(")\n")
        self._finished = True

    def write(self, filename):
        self.finish()
        with open(filename, "w") as fh:
            fh.write(self.text.getvalue())


def _pcb_start_template(
    title,
    date,
    rev,
    company,
    comment1,
    comment2,
    comment3,
    comment4,
    origin_x,
    origin_y,
):
    return f"""
(kicad_pcb (version 20171130) (host pcbnew "(5.1.6-0-10_14)")

  (general
    (thickness 1.6)
    (drawings 6)
    (tracks 0)
    (zones 0)
    (modules 57)
    (nets 1)
  )

  (page USLetter)
  (title_block
    (title "{title}")
    (date "{date}")
    (rev "{rev}")
    (company "{company}")
    (comment 1 "{comment1}")
    (comment 2 "{comment2}")
    (comment 3 "{comment3}")
    (comment 4 "{comment4}")
  )

  (layers
    (0 F.Cu signal hide)
    (31 B.Cu signal hide)
    (36 B.SilkS user)
    (37 F.SilkS user)
    (38 B.Mask user)
    (39 F.Mask user)
    (40 Dwgs.User user)
    (41 Cmts.User user)
    (44 Edge.Cuts user)
  )

  (setup
    (last_trace_width 0.25)
    (trace_clearance 0.2)
    (zone_clearance 0.508)
    (zone_45_only no)
    (trace_min 0.2)
    (via_size 0.8)
    (via_drill 0.4)
    (via_min_size 0.4)
    (via_min_drill 0.3)
    (uvia_size 0.3)
    (uvia_drill 0.1)
    (uvias_allowed no)
    (uvia_min_size 0.2)
    (uvia_min_drill 0.1)
    (edge_width 0.5)
    (segment_width 0.2)
    (pcb_text_width 0.3)
    (pcb_text_size 1.5 1.5)
    (mod_edge_width 0.12)
    (mod_text_size 1 1)
    (mod_text_width 0.15)
    (pad_size 1.524 1.524)
    (pad_drill 0.762)
    (pad_to_mask_clearance 0.05)
    (aux_axis_origin 0 0)
    (grid_origin {origin_x} {origin_y})
    (visible_elements FFFFFF7F)
    (pcbplotparams
      (layerselection 0x010fc_ffffffff)
      (usegerberextensions false)
      (usegerberattributes true)
      (usegerberadvancedattributes true)
      (creategerberjobfile true)
      (excludeedgelayer true)
      (linewidth 0.100000)
      (plotframeref false)
      (viasonmask false)
      (mode 1)
      (useauxorigin false)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (psnegative false)
      (psa4output false)
      (plotreference true)
      (plotvalue true)
      (plotinvisibletext false)
      (padsonsilk false)
      (subtractmaskfromsilk true)
      (outputformat 1)
      (mirror false)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "gerbers"))
  )

  (net 0 "")

  (net_class Default "This is the default net class."
    (clearance 0.2)
    (trace_width 0.25)
    (via_dia 0.8)
    (via_drill 0.4)
    (uvia_dia 0.3)
    (uvia_drill 0.1)
  )
"""


def _drill_template(x, y, d):
    return f"""
        (module Drill:Hole (layer F.Cu) (tedit 60E3390D) (tstamp 60E399A3)
        (at {x:.2f} {y:.2f})
        (descr "drill hole")
        (tags "")
        (attr virtual)
        (pad "" np_thru_hole circle (at 0 0) (size {d:.2f} {d:.2f}) (drill {d:.2f}) (layers *.Cu *.Mask)
        (clearance 0.1) (zone_connect 0))
    )"""


def _outline_template(x, y, width, height):
    return f"""
        (gr_line (start {x:.2f} {y:.2f}) (end {x + width:.2f} {y:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
        (gr_line (start {x + width:.2f} {y:.2f}) (end {x + width:.2f} {y + height:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
        (gr_line (start {x + width:.2f} {y + height:.2f}) (end {x:.2f} {y + height:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
        (gr_line (start {x:.2f} {y + height:.2f}) (end {x:.2f} {y:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
    """


def _horizontal_measurement_template(
    x1,
    y1,
    x2,
    y2,
    length,
    width,
    crossbar_offset,
    arrow_length,
    arrow_span,
    text_size,
    text_thickness,
):
    return f"""
        (dimension {length:.2f} (width 0.15) (layer Dwgs.User)
            (gr_text "{length:.2f} mm" (at {x1 + width / 2:.1f} {y1 - crossbar_offset - math.copysign(1, crossbar_offset):0.1f}) (layer Dwgs.User)
            (effects (font (size {text_size:.2f} {text_size:.2f}) (thickness {text_thickness:.2f})))
            )
            (feature1 (pts (xy {x2:.2f} {y2:.2f}) (xy {x2:.2f} {y2 - crossbar_offset:.2f})))
            (feature2 (pts (xy {x1:.2f} {y1:.2f}) (xy {x1:.2f} {y1 - crossbar_offset:.2f})))
            (crossbar (pts (xy {x1:.2f} {y1 - crossbar_offset:.2f}) (xy {x2:.2f} {y2 - crossbar_offset:.2f})))
            (arrow1a (pts (xy {x2:.2f} {y2 - crossbar_offset:.2f}) (xy {x2 - arrow_length:.2f} {y2 - crossbar_offset - arrow_span:.2f})))
            (arrow1b (pts (xy {x2:.2f} {y2 - crossbar_offset:.2f}) (xy {x2 - arrow_length:.2f} {y2 - crossbar_offset + arrow_span:.2f})))
            (arrow2a (pts (xy {x1:.2f} {y1 - crossbar_offset:.2f}) (xy {x1 + arrow_length:.2f} {y1 - crossbar_offset - arrow_span:.2f})))
            (arrow2b (pts (xy {x1:.2f} {y1 - crossbar_offset:.2f}) (xy {x1 + arrow_length:.2f} {y1 - crossbar_offset + arrow_span:.2f})))
        )
        """


def _vertical_measurement_template(
    x1,
    y1,
    x2,
    y2,
    length,
    height,
    crossbar_offset,
    arrow_length,
    arrow_span,
    text_size,
    text_thickness,
):
    orientation = 90 if crossbar_offset < 1 else 270
    return f"""
    (dimension {length:.2f} (width 0.15) (layer Dwgs.User)
        (gr_text "{length:.2f} mm" (at {x1 + crossbar_offset + math.copysign(1, crossbar_offset):.1f} {y1 + height / 2:.1f} {orientation}) (layer Dwgs.User)
        (effects (font (size {text_size:.2f} {text_size:.2f}) (thickness {text_thickness:.2f})))
        )
        (feature1 (pts (xy {x2:.2f} {y2:.2f}) (xy {x2 + crossbar_offset:.2f} {y2:.2f})))
        (feature2 (pts (xy {x1:.2f} {y1:.2f}) (xy {x1 + crossbar_offset:.2f} {y1:.2f})))
        (crossbar (pts (xy {x1 + crossbar_offset:.2f} {y1:.2f}) (xy {x2 + crossbar_offset:.2f} {y2:.2f})))
        (arrow1a (pts (xy {x2 + crossbar_offset:.2f} {y2:.2f}) (xy {x2 + crossbar_offset - arrow_span:.2f} {y2 - arrow_length:.2f})))
        (arrow1b (pts (xy {x2 + crossbar_offset:.2f} {y2:.2f}) (xy {x2 + crossbar_offset + arrow_span:.2f} {y2 - arrow_length:.2f})))
        (arrow2a (pts (xy {x1 + crossbar_offset:.2f} {y1:.2f}) (xy {x1 + crossbar_offset - arrow_span:.2f} {y1 + arrow_length:.2f})))
        (arrow2b (pts (xy {x1 + crossbar_offset:.2f} {y1:.2f}) (xy {x1 + crossbar_offset + arrow_span:.2f} {y1 + arrow_length:.2f})))
    )
    """


def _slotted_hole_template(x, y, hole_size, slot_size):
    return f"""
    (module Drill:SlottedHole (layer F.Cu) (tedit 5E5DD340)
        (at {x:.2f} {y:.2f})
        (descr "Drill {hole_size:.1f} mm, slotted")
        (tags "")
        (attr virtual)
        (pad "" np_thru_hole roundrect (at 0 0) (size {slot_size:.2f} {hole_size:.2f}) (drill oval {slot_size:.2f} {hole_size:.1f}) (layers *.Cu *.Mask) (roundrect_rratio 0.5) (clearance 0.1) (zone_connect 0))
    )
"""
