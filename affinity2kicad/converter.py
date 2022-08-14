# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import concurrent.futures
import os.path

import svgpathtools
import rich
import rich.live
import rich.text

from . import trace

console = rich.get_console()

LAYERS = {
    "FSilkS": "F.SilkS",
    "BSilkS": "B.SilkS",
    "FCu": "F.Cu",
    "BCu": "B.Cu",
    "FMask": "F.Mask",
    "BMask": "B.Mask",
}


class Converter:
    def __init__(self, doc, pcb):
        self.doc = doc
        self.pcb = pcb
        self.bbox = (0, 0, 0, 0)
        self._tmpdir = os.path.join(".", ".cache")
        os.makedirs(self._tmpdir, exist_ok=True)

    def convert(self, drills=True, layers=True):
        self.convert_outline()
        if drills:
            self.convert_drills()
        if layers:
            self.convert_layers()

    def convert_outline(self):
        if self._convert_outline_rect():
            return

        if not self._convert_outline_paths():
            raise ValueError("Unable to create board outline")

    def _convert_outline_rect(self):
        # Simplest case - the outline is just a rectangle.
        rects = list(self.doc.query_all("#EdgeCuts rect")) + list(self.doc.query_all("rect#EdgeCuts"))

        if not rects:
            return None

        # First, find the largest rectangle. That one is our outline.
        bbox = [0, 0, 0, 0]

        for rect in rects:
            x = self.doc.to_mm(rect.get("screen_x"), 1)
            y = self.doc.to_mm(rect.get("screen_y"), 1)
            width = self.doc.to_mm(rect.get("screen_width"), 1)
            height = self.doc.to_mm(rect.get("screen_height"), 1)
            if width * height > bbox[2] * bbox[3]:
                bbox = [x, y, width, height]

        if bbox[0] != 0 or bbox[1] != 0:
            raise ValueError("Edge.Cuts x,y is not 0,0.")

        self.bbox = (
            self.pcb.page_width / 2 - bbox[2],
            self.pcb.page_height / 2 - bbox[3] / 2,
            bbox[2],
            bbox[3],
        )

        console.print(
            f"Design outline is [green underline]rectangular[/green underline], bounding box is [green][bold]{bbox[2]:.2f} mm x {bbox[3]:.2f} mm[/bold]."
        )

        # Now that the PCB offset is known, we can start building the PCB.
        self.pcb.bbox = self.bbox
        self.pcb.offset = self.bbox[:2]
        self.pcb.start()
        self.pcb.add_horizontal_measurement(0, 0, self.bbox[2], 0)
        self.pcb.add_vertical_measurement(0, 0, 0, self.bbox[3])

        # Draw all of the rects onto the PCB
        for rect in rects:
            x = self.doc.to_mm(rect.get("screen_x"), 1)
            y = self.doc.to_mm(rect.get("screen_y"), 1)
            width = self.doc.to_mm(rect.get("screen_width"), 1)
            height = self.doc.to_mm(rect.get("screen_height"), 1)
            self.pcb.add_outline(x, y, width, height)
            console.print(
                f"- [green]X: {x:.1f} mm, Y: {y:.1f} mm, W: {width:.1f} mm H: {height:.1f} mm"
            )

        console.print()
        return True

    def _convert_outline_paths(self):
        # Complex case - edge cuts is a path
        edge_cuts = list(self.doc.query_all("#EdgeCuts"))[0]

        if edge_cuts.local_name == "g":
            edge_cuts = list(self.doc.query_all("#EdgeCuts path"))[0]

        if edge_cuts.local_name != "path":
            raise ValueError("Edge cuts is not a path")

        path = svgpathtools.parse_path(edge_cuts.get("d"))
        pathbbox = path.bbox()
        bbox = [
            self.doc.to_mm(n)
            for n in (pathbbox[0], pathbbox[2], pathbbox[1], pathbbox[3])
        ]

        if bbox[0] != 0 or bbox[1] != 0:
            raise ValueError(f"Edge.Cuts x,y is not 0,0, found {bbox}")

        self.bbox = (
            self.pcb.page_width / 2 - bbox[2],
            self.pcb.page_height / 2 - bbox[3] / 2,
            bbox[2],
            bbox[3],
        )

        console.print(
            f"Design outline is [bold underline purple]non-rectangular[/bold underline purple], bounding box is [green][bold]{bbox[2]:.2f} mm x {bbox[3]:.2f} mm[/bold]."
        )
        console.print()

        # Now that the PCB offset is known, we can start building the PCB.
        self.pcb.bbox = self.bbox
        self.pcb.offset = self.bbox[:2]
        self.pcb.start()
        self.pcb.add_horizontal_measurement(0, 0, self.bbox[2], 0)
        self.pcb.add_vertical_measurement(0, 0, 0, self.bbox[3])

        # Go through each path segment and add it to the PCB.
        segments = [
            _quad_bezier_to_arc(seg)
            if isinstance(seg, svgpathtools.CubicBezier)
            else seg
            for seg in path
        ]

        for seg in segments:
            if isinstance(seg, svgpathtools.Line):
                self.pcb.add_line(
                    self.doc.to_mm(seg.start.real, 2),
                    self.doc.to_mm(seg.start.imag, 2),
                    self.doc.to_mm(seg.end.real, 2),
                    self.doc.to_mm(seg.end.imag, 2),
                )

            elif isinstance(seg, svgpathtools.Arc):
                self.pcb.add_arc(
                    self.doc.to_mm(seg.center.real, 2),
                    self.doc.to_mm(seg.center.imag, 2),
                    self.doc.to_mm(seg.end.real, 2),
                    self.doc.to_mm(seg.end.imag, 2),
                    seg.rotation,
                )

            else:
                raise ValueError(f"Can't convert path segment {seg}.")

        return True

    def convert_drills(self):
        circles = list(self.doc.query_all("#Drill circle"))

        if not circles:
            console.print("[yellow]No drills found")

        console.print(f"Converting {len(circles)} drills:")

        for el in circles:
            x = self.doc.to_mm(el.get("screen_cx"))
            y = self.doc.to_mm(el.get("screen_cy"))
            d = self.doc.to_mm(float(el.get("screen_r")) * 2)

            self.pcb.add_drill(x, y, d)

            console.print(f"- [green]X: {x:.1f} mm, Y: {y:.1f} mm, D: {d:.2f} mm")

        console.print()

    def convert_layers(self):
        console.print("Converting graphic layers:")
        results = {k: "..." for k in LAYERS.keys()}

        status = "\n".join(f"- {name}: {status}" for name, status in results.items())

        with rich.live.Live(rich.text.Text.from_markup(status)) as live_status:
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = [
                    executor.submit(convert_layer, self.doc, self._tmpdir, src, dst)
                    for src, dst in LAYERS.items()
                ]

                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    layer_name, mod, cached = result

                    if mod:
                        self.pcb.add_mod(mod, 0, 0)
                        if cached:
                            results[layer_name] = "[blue]cached[/blue]"
                        else:
                            results[layer_name] = "[green]done[/green]"
                    else:
                        results[layer_name] = "[yellow]empty[/yellow]"

                    status = "\n".join(
                        f"- {name}: {status}" for name, status in results.items()
                    )
                    live_status.update(rich.text.Text.from_markup(status))

        console.print()

    @property
    def centroid(self):
        return self.bbox[0] + (self.bbox[2] / 2), self.bbox[1] + (self.bbox[3] / 2)


def convert_layer(doc, tmpdir, src_layer_name, dst_layer_name):
    svg_filename = os.path.join(tmpdir, f"output-{dst_layer_name}.svg")
    png_filename = os.path.join(tmpdir, f"output-{dst_layer_name}.png")
    mod_filename = os.path.join(tmpdir, f"output-{dst_layer_name}.kicad_mod")

    doc = doc.copy()

    if not doc.remove_layers(keep=[src_layer_name]):
        return src_layer_name, None, False

    doc.recolor(src_layer_name)
    svg_text = doc.tostring()

    # See if the cached layer hasn't changed, if so, don't bother re-rendering.
    if os.path.exists(mod_filename) and os.path.exists(svg_filename):
        with open(svg_filename, "r") as fh:
            cached_svg_text = fh.read()

        if svg_text.strip() == cached_svg_text.strip():
            return src_layer_name, mod_filename, True

    # No cached version, so render it and convert it.
    with open(svg_filename, "w") as fh:
        fh.write(svg_text)

    doc.render(png_filename)

    image = trace.load_image(png_filename)
    bitmap = trace.prepare_image(image, invert=False, threshold=127)
    polys = trace.trace_to_polys(bitmap)
    fp = trace.generate_footprint(polys=polys, dpi=doc.dpi, layer=dst_layer_name)

    with open(mod_filename, "w") as fh:
        fh.write(fp)

    return src_layer_name, mod_filename, False


def _quad_bezier_to_arc(b):
    bbox = [round(n, 2) for n in b.bbox()]
    xmin, xmax, ymin, ymax = bbox

    # Start and end *must* lie on the corners of the bounding box.
    # Figure out which corner is the starting corner.

    if round(b.start.real, 2) not in bbox:
        return
    if round(b.start.imag, 2) not in bbox:
        return
    if round(b.end.real, 2) not in bbox:
        return
    if round(b.end.imag, 2) not in bbox:
        return

    # Check if this is just a line.
    if b.start == b.control1 and b.end == b.control2:
        return svgpathtools.Line(b.start, b.end)

    # Start and end must be on opposite corners
    if round(b.start.real, 2) == round(b.end.real, 2):
        return
    if round(b.start.imag, 2) == round(b.end.imag, 2):
        return

    radius = complex(xmax - xmin, ymax - ymin)

    arc = svgpathtools.Arc(
        start=b.start, radius=radius, rotation=90, large_arc=0, sweep=0, end=b.end
    )

    return arc
