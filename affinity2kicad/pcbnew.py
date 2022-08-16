# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import io
import datetime


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
        self.date = datetime.date.today().strftime("%Y-%m-%d")
        self.company = "Winterbloom"
        self.comment1 = "Alethea Flowers"
        self.comment2 = "CC BY-NC-ND 4.0"
        self.comment3 = ""
        self.comment4 = ""
        self.bbox = (0, 0, 0, 0)

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
        text_size=1,
        text_thickness=0.15,
        below=False,
    ):
        value = round(x2 - x1, 2)
        x1 += self.offset[0]
        y1 += self.offset[1]
        x2 += self.offset[0]
        y2 += self.offset[1]
        self.text.write(
            _aligned_measurement_template(
                x1,
                y1,
                x2,
                y2,
                value=value,
                height=3 if below else -3,
                text_size=text_size,
                text_thickness=text_thickness
            )
        )

    def add_vertical_measurement(
        self,
        x1,
        y1,
        x2,
        y2,
        text_size=1,
        text_thickness=0.15,
        right=False,
    ):
        value = round(y2 - y1, 2)
        x1 += self.offset[0]
        y1 += self.offset[1]
        x2 += self.offset[0]
        y2 += self.offset[1]
        self.text.write(
            _aligned_measurement_template(
                x1,
                y1,
                x2,
                y2,
                value=value,
                height=-3 if right else 3,
                text_size=text_size,
                text_thickness=text_thickness
            )
        )

    def add_mod(self, filename_or_text, x, y, orientation=0, relative=True):
        if relative:
            x += self.offset[0]
            y += self.offset[1]

        if filename_or_text.startswith("(footprint"):
            mod = filename_or_text
        else:
            mod = open(filename_or_text, "r").read()

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
(kicad_pcb (version 20211014) (generator affinity2kicad)

  (general
    (thickness 1.6)
  )

  (paper "USLetter")
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
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (44 "Edge.Cuts" user)
  )

  (setup
    (pad_to_mask_clearance 0.05)
    (grid_origin {origin_x:0.4f} {origin_y:0.4f})
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (disableapertmacros false)
      (usegerberextensions false)
      (usegerberattributes true)
      (usegerberadvancedattributes true)
      (creategerberjobfile true)
      (svguseinch false)
      (svgprecision 6)
      (excludeedgelayer true)
      (plotframeref false)
      (viasonmask false)
      (mode 1)
      (useauxorigin false)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (dxfpolygonmode true)
      (dxfimperialunits true)
      (dxfusepcbnewfont true)
      (psnegative false)
      (psa4output false)
      (plotreference true)
      (plotvalue true)
      (plotinvisibletext false)
      (sketchpadsonfab false)
      (subtractmaskfromsilk true)
      (outputformat 1)
      (mirror false)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "gerbers")
    )
  )

  (net 0 "")
"""


def _drill_template(x, y, d):
    return f"""
        (footprint "Drill:Hole" (layer "F.Cu")
            (tedit 60E3390D) (tstamp 00000000-0000-0000-0000-000060e399a3)
            (at {x:.2f} {y:.2f})
            (descr "drill hole")
            (attr exclude_from_pos_files exclude_from_bom)
            (pad "" np_thru_hole circle locked
                (at 0 0)
                (size {d:.2f} {d:.2f})
                (drill {d:.2f})
                (layers *.Cu *.Mask)
                (clearance 0.1)
                (zone_connect 0)
                (tstamp ad4de56d-a553-4c14-9eba-511eb66d077a)
            )
        )
    """


def _outline_template(x, y, width, height):
    return f"""
        (gr_line (start {x:.2f} {y:.2f}) (end {x + width:.2f} {y:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
        (gr_line (start {x + width:.2f} {y:.2f}) (end {x + width:.2f} {y + height:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
        (gr_line (start {x + width:.2f} {y + height:.2f}) (end {x:.2f} {y + height:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
        (gr_line (start {x:.2f} {y + height:.2f}) (end {x:.2f} {y:.2f}) (layer Edge.Cuts) (width 0.5) (tstamp 60E39A33))
    """


def _aligned_measurement_template(
    x1,
    y1,
    x2,
    y2,
    value,
    height=3,
    text_size=1.27,
    text_thickness=0.15
):
    return f"""
    (dimension
        (type aligned)
        (layer "Dwgs.User")
        (tstamp 0557ead8-3208-42e1-b732-3b72dd768ea0)
        (pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f}))
        (height {height:0.2f})
        (gr_text "{value:.2f} mm"
            (at {x1:.1f} {y1 + height / 2:.1f})
            (layer "Dwgs.User")
            (tstamp 0557ead8-3208-42e1-b732-3b72dd768ea0)
            (effects
                (font (size {text_size:.2f} {text_size:.2f}) (thickness {text_thickness:.2f}))
            )
        )
        (format (units 2) (units_format 1) (precision 2))
        (style
            (thickness {text_thickness:0.2f})
            (arrow_length 1.27)
            (text_position_mode 0)
            (extension_height 0.58642)
            (extension_offset 0)
            keep_text_aligned
        )
    )
    """


def _slotted_hole_template(x, y, hole_size, slot_size):
    return f"""
    (footprint "Drill:SlottedHole" (layer "F.Cu")
        (tedit 5E5DD340) (tstamp c95cceac-2fea-43fe-8192-7e6abff6f933)
        (at {x:.2f} {y:.2f})
        (descr "Drill {hole_size:.1f} mm, slotted")
        (attr exclude_from_pos_files exclude_from_bom)
        (pad "" np_thru_hole roundrect locked
            (at 0 0)
            (size {slot_size:.2f} {hole_size:.2f})
            (drill oval {slot_size:.2f} {hole_size:.1f})
            (layers *.Cu *.Mask)
            (roundrect_rratio 0.5)
            (clearance 0.1)
            (zone_connect 0)
            (tstamp b2aa81b7-537d-4634-9f80-971e9b57325b)
        )
    )
"""
