# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import concurrent.futures
import os.path

import rich
from rich import print
import rich.live
import rich.text
import svgpathtools
import svgpathtools.svg_to_paths

from . import document, pcb, trace, geometry

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
    def __init__(self, doc: document.SVGDocument, pcb: pcb.PCB):
        self.doc = doc
        self.pcb = pcb
        self.bbox = (0, 0, 0, 0)
        self.workdir = os.path.join(".", ".cache")
        os.makedirs(self.workdir, exist_ok=True)

    @property
    def centroid(self):
        return self.bbox[0] + (self.bbox[2] / 2), self.bbox[1] + (self.bbox[3] / 2)

    def convert(self, drills: bool = True, layers: bool = True):
        self.convert_outline()
        if drills:
            self.convert_drills()
        if layers:
            self.convert_layers()

    def convert_outline(self):
        print("\n[bold]Converting board outline:")

        # Pluck EdgeCuts elements from the SVG. There's a few cases here:
        edge_cuts_elem = list(self.doc.query_all("#EdgeCuts"))[0]

        # First case: #EdgeCuts is a single shape element. In this case,
        # make it into a list so it can be processed as the second case.
        if edge_cuts_elem.local_name in (
            "path",
            "rect",
            "circle",
            "polygon",
            "ellipse",
        ):
            edge_cuts_elems = [edge_cuts_elem]

        # Second case: #EdgeCuts is a group of shape elements. This is how
        # we want to process things, so just get a list of all its children.
        elif edge_cuts_elem.local_name == "g":
            edge_cuts_elems = edge_cuts_elem.iter_children()

        # Third case: #EdgeCuts is something else, so give up.
        else:
            raise ValueError(
                f"Unable to convert {edge_cuts_elem.local_name}, unknown tag"
            )

        # Convert all edge cut shapes to paths.
        paths: list[float, tuple(float, float, float, float), svgpathtools.Path] = []

        for elem, path in geometry.svg_elements_to_paths(edge_cuts_elems):
            if path is None:
                print(f"- [red] Not converting unknown element {elem.local_name}")
                continue

            brect = list(self.doc.iter_to_mm(geometry.bbox_to_rect(*path.bbox())))

            # Note: using approximate area based on just the bounding box,
            # since it isn't necessary for our purposes to know the area of the
            # actual curve, just the area of its bbox.
            area = round(abs(brect[2] * brect[3]))

            paths.append((area, brect, path))

            print(f"- Converted [cyan]{elem.local_name}[/cyan] with {len(path)} segments, bounding rect {brect}, and area of {area} mm^2")

        if not paths:
            raise ValueError("No paths found on EdgeCuts!")

        # Figure out the bounding box (path) of the design so that the offset
        # can be determined. The path with the largest bounding box area is the
        # board bounding box.
        paths.sort(key=lambda p: p[0], reverse=True)

        bounding_area, bounding_brect, bounding_path = paths[0]

        print()
        if bounding_brect[0] != 0 or bounding_brect[1] != 0:
            print(
                f"[yellow]Board outline bounding box does not start at 0, 0, found {bounding_brect}"
            )

        console.print(
            f"[green]Overall board size is [cyan][bold]{bounding_brect[2]:.2f} mm x {bounding_brect[3]:.2f} mm[/bold]."
        )

        self.bbox = (
            self.pcb.page_width / 2 - bounding_brect[2],
            self.pcb.page_height / 2 - bounding_brect[3] / 2,
            bounding_brect[2],
            bounding_brect[3],
        )

        # Now that the bounding box and offset are known, we can start adding
        # items to the PCB
        self.pcb.bbox = self.bbox
        self.pcb.offset = self.bbox[:2]

        # Horizontal and vertical measurements for the board bounding box
        self.pcb.add_horizontal_measurement(0, 0, self.bbox[2], 0)
        self.pcb.add_vertical_measurement(0, 0, 0, self.bbox[3])

        # Add all paths as polygons
        for _, _, path in paths:
            points = self.doc.points_to_mm(geometry.path_to_points(path))
            self.pcb.add_poly(points, layer="Edge.Cuts", width=0.5, fill=False)

        return True

    def convert_drills(self):
        console.print("\n[bold]Converting drills:")

        drill_elms = list(self.doc.query_all("#Drill *"))

        count = 0
        for el in drill_elms:
            if el.local_name != "circle":
                print(f"- [red] Non-circular element not converted: {el}")
                continue

            x = self.doc.to_mm(el.get("screen_cx"))
            y = self.doc.to_mm(el.get("screen_cy"))
            d = self.doc.to_mm(float(el.get("screen_r")) * 2)

            self.pcb.add_drill(x, y, d)

            console.print(f"- X: {x:.1f} mm, Y: {y:.1f} mm, D: {d:.2f} mm")
            count += 1

        if count:
            console.print(f"\n[green]Converted [cyan]{count}[/cyan] drills")
        else:
            console.print("\n[yellow]No drills found")

    def convert_layers(self):
        console.print("\n[bold]Converting graphic layers:")
        results = {k: "..." for k in LAYERS.keys()}

        status = "\n".join(f"- {name}: {status}" for name, status in results.items())

        with rich.live.Live(rich.text.Text.from_markup(status)) as live_status:
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = [
                    executor.submit(
                        convert_layer_thread, self.doc, self.workdir, self.pcb.offset, src, dst
                    )
                    for src, dst in LAYERS.items()
                ]

                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    layer_name, footprint, cached = result

                    if footprint:
                        with open(footprint, "r") as fh:
                            self.pcb.add_literal(fh.read())

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


def convert_layer_thread(doc, tmpdir, position, src_layer_name, dst_layer_name):
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
    fp = trace.generate_footprint(
        polys=polys, dpi=doc.dpi, layer=dst_layer_name, position=position
    )

    with open(mod_filename, "w") as fh:
        fh.write(fp)

    return src_layer_name, mod_filename, False
