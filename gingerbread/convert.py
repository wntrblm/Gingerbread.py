# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import argparse
import concurrent.futures
import datetime
import os.path
import pathlib
import sys

import rich
import rich.live
import rich.text
import svgpathtools
import svgpathtools.svg_to_paths

from . import _document, _geometry, pcb, trace
from ._print import set_verbose, print, printv
from ._utils import default_param_value

console = rich.get_console()

LAYERS = {
    "FSilkS": "F.SilkS",
    "BSilkS": "B.SilkS",
    "FCu": "F.Cu",
    "BCu": "B.Cu",
    "FMask": "F.Mask",
    "BMask": "B.Mask",
}


class ConversionError(RuntimeError):
    pass


class Converter:
    def __init__(self, doc: _document.SVGDocument, pcb: pcb.PCB):
        self.doc = doc
        self.pcb = pcb
        self.bbox = (0, 0, 0, 0)
        self.workdir = os.path.join(".", ".cache")
        os.makedirs(self.workdir, exist_ok=True)

    @property
    def centroid(self):
        return self.bbox[0] + (self.bbox[2] / 2), self.bbox[1] + (self.bbox[3] / 2)

    def convert(self, outline: bool = True, drills: bool = True, layers: bool = True):
        if outline:
            self.convert_outline()
        if drills:
            self.convert_drills()
        if layers:
            self.convert_layers()

    def convert_outline(self):
        print("[bold]Converting board outline")

        # Find the edgecuts layer
        edge_cuts_layer = list(self.doc.query_all("#EdgeCuts"))

        if len(edge_cuts_layer) == 0:
            raise ConversionError("EdgeCuts layer not found")
        if len(edge_cuts_layer) > 1:
            raise ConversionError("Multiple elements named EdgeCuts found")

        edge_cuts_layer = edge_cuts_layer[0]

        # Pluck EdgeCuts elements from the SVG. There's a few cases here:
        # First case: #EdgeCuts is a single shape element. In this case,
        # make it into a list so it can be processed as the second case.
        if edge_cuts_layer.local_name in (
            "path",
            "rect",
            "circle",
            "polygon",
            "ellipse",
        ):
            edge_cuts_elems = [edge_cuts_layer]

        # Second case: #EdgeCuts is a group of shape elements. This is how
        # we want to process things, so just get a list of all its children.
        elif edge_cuts_layer.local_name == "g":
            edge_cuts_elems = edge_cuts_layer.iter_children()

        # Third case: #EdgeCuts is something else, so give up.
        else:
            raise ConversionError(
                f"Unable to convert {edge_cuts_layer.local_name}, unknown tag"
            )

        # Convert all edge cut shapes to paths. The items in the tuple are
        # area, brect, and the parsed path.
        paths: list[float, tuple(float, float, float, float), svgpathtools.Path] = []

        for elem, path in _geometry.svg_elements_to_paths(edge_cuts_elems):
            if path is None:
                print(f"- [red] Not converting unknown element {elem.local_name}")
                continue

            brect = list(self.doc.iter_to_mm(_geometry.bbox_to_rect(*path.bbox())))

            # Note: using approximate area based on just the bounding box,
            # since it isn't necessary for our purposes to know the area of the
            # actual curve, just the area of its bbox.
            area = round(abs(brect[2] * brect[3]))

            paths.append((area, brect, path))

            printv(
                f"- Converted [cyan]{elem.local_name}[/cyan] with {len(path)} segments, bounding rect {brect}, and area of {area:.2f} mm²"
            )

        if not paths:
            raise ConversionError("No paths found on EdgeCuts!")

        # Figure out the bounding box (path) of the design so that the offset
        # can be determined. The path with the largest bounding box area is the
        # board bounding box.
        paths.sort(key=lambda p: p[0], reverse=True)

        bounding_area, bounding_brect, bounding_path = paths[0]

        if bounding_brect[0] != 0 or bounding_brect[1] != 0:
            print(
                f"[yellow]Warning[/yellow]: board outline bounding box does not start at 0, 0, found {bounding_brect}"
            )

        print(
            f"[green]Outline converted[/green]: overall board size is [cyan][bold]{bounding_brect[2]:.2f} mm x {bounding_brect[3]:.2f} mm[/bold][/cyan] ({bounding_area:.2f} mm²)."
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
            points = self.doc.points_to_mm(_geometry.path_to_points(path))
            self.pcb.add_poly(points, layer="Edge.Cuts", width=0.5, fill=False)

        return True

    def convert_drills(self):
        print("[bold]Converting drills")

        drill_elms = list(self.doc.query_all("#Drill *"))

        count = 0
        for el in drill_elms:
            if el.local_name != "circle":
                print(
                    f"- [yellow]Warning:[/yellow] non-circular element {el.local_name} not converted."
                )
                continue

            x = self.doc.to_mm(el.get("cx"))
            y = self.doc.to_mm(el.get("cy"))
            d = self.doc.to_mm(float(el.get("r")) * 2)

            self.pcb.add_drill(x, y, d)

            printv(f"- Drill @ ({x:.2f}, {y:.2f}) mm, ⌀ {d:.2f} mm")
            count += 1

        if count:
            print(f"[green]Drills converted[/green]: [cyan]{count}[/cyan]")
        else:
            print("[yellow]No drills found")

    def convert_layers(self):
        print("[bold]Converting graphic layers")
        results = {k: "..." for k in LAYERS.keys()}

        status = "\n".join(f"- {name}: {status}" for name, status in results.items())

        with rich.live.Live(rich.text.Text.from_markup(status)) as live_status:
            with concurrent.futures.ProcessPoolExecutor() as executor:
                futures = [
                    executor.submit(
                        _convert_layer_thread,
                        self.doc,
                        self.workdir,
                        self.pcb.offset,
                        src,
                        dst,
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


def _convert_layer_thread(doc, tmpdir, position, src_layer_name, dst_layer_name):
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


def convert(
    *,
    source: os.PathLike,
    title: str = "",
    rev: str = "v1",
    date: str = datetime.date.today().strftime("%Y-%m-%d"),
    company: str = "",
    comment1: str = "",
    comment2: str = "",
    comment3: str = "",
    comment4: str = "",
    dpi: float = 2540,
    outline: bool = True,
    drills: bool = True,
    layers: bool = True,
):
    doc = _document.SVGDocument(source, dpi=dpi)
    pcb_ = pcb.PCB(
        title=title,
        rev=rev,
        date=date,
        company=company,
        comment1=comment1,
        comment2=comment2,
        comment3=comment3,
        comment4=comment4,
    )

    convert = Converter(doc, pcb_)
    convert.convert(outline=outline, drills=drills, layers=layers)

    return pcb_


def main():
    parser = argparse.ArgumentParser(
        "convert", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("dest", nargs="?", type=pathlib.Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")

    parser.add_argument("--title", default=default_param_value(convert, "title"))
    parser.add_argument("--rev", default=default_param_value(convert, "rev"))
    parser.add_argument("--date", default=default_param_value(convert, "date"))
    parser.add_argument(
        "--company", type=str, default=default_param_value(convert, "company")
    )
    parser.add_argument(
        "--comment1", type=str, default=default_param_value(convert, "comment1")
    )
    parser.add_argument(
        "--comment2", type=str, default=default_param_value(convert, "comment2")
    )
    parser.add_argument(
        "--comment3", type=str, default=default_param_value(convert, "comment3")
    )
    parser.add_argument(
        "--comment4", type=str, default=default_param_value(convert, "comment4")
    )
    parser.add_argument(
        "--dpi", type=float, default=default_param_value(convert, "dpi")
    )
    parser.add_argument(
        "--outline",
        action=argparse.BooleanOptionalAction,
        default=default_param_value(convert, "outline"),
    )
    parser.add_argument(
        "--drills",
        action=argparse.BooleanOptionalAction,
        default=default_param_value(convert, "drills"),
    )
    parser.add_argument(
        "--layers",
        action=argparse.BooleanOptionalAction,
        default=default_param_value(convert, "drills"),
    )

    args = parser.parse_args()

    if args.dest is None:
        args.dest = args.source.with_suffix(".kicad_pcb")

    set_verbose(args.verbose)

    pcb_ = convert(
        source=args.source,
        title=args.title,
        rev=args.rev,
        date=args.date,
        company=args.company,
        comment1=args.comment1,
        comment2=args.comment2,
        comment3=args.comment3,
        comment4=args.comment4,
        dpi=args.dpi,
        outline=args.outline,
        drills=args.drills,
        layers=args.layers,
    )

    with open(args.dest, "w") as fh:
        pcb_.write(fh)

    rich.print(f"[green]Written to {args.dest} :purple_heart:", file=sys.stderr)


if __name__ == "__main__":
    main()
