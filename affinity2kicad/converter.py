# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import concurrent.futures
import os.path

import svgpathtools
import rich
import rich.live
import rich.text

from affinity2kicad import pcbnew

from . import trace
from ._utils import bezier_to_points

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
    def __init__(self, doc, pcb: pcbnew.PCB):
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

        points = []

        for seg in path:
            if isinstance(seg, svgpathtools.Line):
                points.append((self.doc.to_mm(seg.start.real, 2), self.doc.to_mm(seg.start.imag, 2)))
                points.append((self.doc.to_mm(seg.end.real, 2), self.doc.to_mm(seg.end.imag, 2)))

            elif isinstance(seg, svgpathtools.CubicBezier):
                for point in bezier_to_points(
                    (seg.start.real, seg.start.imag),
                    (seg.control1.real, seg.control1.imag),
                    (seg.control2.real, seg.control2.imag),
                    (seg.end.real, seg.end.imag),
                    delta=1
                ):
                    points.append((self.doc.to_mm(point[0]), self.doc.to_mm(point[1])))

            elif seg is None:
                print("Hmm, there was an empty segment?")
                pass

            else:
                raise ValueError(f"Can't convert path segment {seg}.")

        self.pcb.add_poly(points, layer="Edge.Cuts")

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

    image = trace._load_image(png_filename)
    bitmap = trace._prepare_image(image, invert=False, threshold=127)
    polys = trace._trace_bitmap_to_polys(bitmap, center=False)
    fp = trace.generate_footprint(polys=polys, dpi=doc.dpi, layer=dst_layer_name)

    with open(mod_filename, "w") as fh:
        fh.write(fp)

    return src_layer_name, mod_filename, False
