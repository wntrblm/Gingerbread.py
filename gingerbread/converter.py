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

from . import document, pcb, trace
from ._utils import path_to_points

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
        edge_cuts_elem = list(self.doc.query_all("#EdgeCuts"))[0]

        if edge_cuts_elem.local_name in (
            "path",
            "rect",
            "circle",
            "polygon",
            "ellipse",
        ):
            edge_cuts_elems = [edge_cuts_elem]
        elif edge_cuts_elem.local_name == "g":
            edge_cuts_elems = list(self.doc.query_all("#EdgeCuts *"))
        else:
            raise ValueError(
                f"Unable to convert {edge_cuts_elem.local_name}, unknown tag"
            )

        # Convert all shapes to paths.
        # Based on svgpathtools.svg2paths
        paths: list[svgpathtools.Path] = []

        for elem in edge_cuts_elems:
            path = None

            match elem.local_name:
                case "rect":
                    path = svgpathtools.parse_path(svgpathtools.svg_to_paths.rect2pathd(elem))
                case "polygon":
                    path = svgpathtools.parse_path(svgpathtools.svg_to_paths.polygon2pathd(elem))
                case "circle" | "ellipse":
                    path = svgpathtools.parse_path(svgpathtools.svg_to_paths.ellipse2pathd(elem))
                case "path":
                    path = svgpathtools.parse_path(elem.get("d"))
                case _:
                    print(f"- [red] Not converting unknown element {elem.local_name}")

            if path is None:
                continue

            bbox = list(self.doc.iter_to_mm(path.bbox()))
            paths.append(path)
            print(f"- Converted {elem.local_name} with bounding box {bbox}")

        if not paths:
            raise ValueError("No paths found on EdgeCuts!")

        # Figure out the bounding box (path) of the design so that the offset
        # can be determined. The path with the largest area is the board
        # bounding box.
        paths.sort(key=lambda p: abs(p.area()), reverse=True)

        bounding_path = paths[0]

        pathbbox = bounding_path.bbox()
        bbox = [
            self.doc.to_mm(n)
            for n in (pathbbox[0], pathbbox[2], pathbbox[1], pathbbox[3])
        ]

        if bbox[0] != 0 or bbox[1] != 0:
            print("[yellow] Board outline bounding box does not start at 0, 0, found {bbox[:2]}")

        self.bbox = (
            self.pcb.page_width / 2 - bbox[2],
            self.pcb.page_height / 2 - bbox[3] / 2,
            bbox[2],
            bbox[3],
        )

        console.print(
            f"\n[green]Overall board size is [cyan][bold]{bbox[2]:.2f} mm x {bbox[3]:.2f} mm[/bold]."
        )

        # Now that the bounding box and offset are known, we can start adding
        # items to the PCB
        self.pcb.bbox = self.bbox
        self.pcb.offset = self.bbox[:2]

        # Horizontal and vertical measurements for the board bounding box
        self.pcb.add_horizontal_measurement(0, 0, self.bbox[2], 0)
        self.pcb.add_vertical_measurement(0, 0, 0, self.bbox[3])

        # Add all paths as polygons
        for path in paths:
            points = self.doc.points_to_mm(path_to_points(path))
            self.pcb.add_poly(points, layer="Edge.Cuts", width=0.5, fill=False)

        return True

    def convert_drills(self):
        console.print("\n[bold]Converting drills:")

        drill_elms = list(self.doc.query_all("#Drill *"))

        if not drill_elms:
            console.print("[yellow]No drills found")

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

        console.print(f"\n[green]Converted [cyan]{count}[/cyan] drills")

    def convert_layers(self):
        console.print("\n[bold]Converting graphic layers:")
        results = {k: "..." for k in LAYERS.keys()}

        status = "\n".join(f"- {name}: {status}" for name, status in results.items())

        with rich.live.Live(rich.text.Text.from_markup(status)) as live_status:
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = [
                    executor.submit(
                        convert_layer, self.doc, self.workdir, self.pcb.offset, src, dst
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


def convert_layer(doc, tmpdir, position, src_layer_name, dst_layer_name):
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
