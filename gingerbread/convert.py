# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import argparse
import datetime
import pathlib
import sys

import svgpathtools
import svgpathtools.svg_to_paths

from . import _geometry, _svg_document, pcb, trace
from ._print import print, printv, set_timing, set_verbose
from ._utils import compare_file_to_string, default_param_value

_EDGE_LAYERS = ("Edge.Cuts", "EdgeCuts", "Outline")
_DRILL_LAYERS = ("Drill", "Drills")
_GRAPHIC_LAYERS = {
    "F.SilkS": ("F.SilkS", "FSilkS", "F.Silk", "FSilk"),
    "B.SilkS": ("B.SilkS", "BSilkS", "B.Silk", "BSilk"),
    "F.Cu": ("F.Cu", "FCu"),
    "B.Cu": ("B.Cu", "BCu"),
    "F.Mask": ("F.Mask", "FMask"),
    "B.Mask": ("B.Mask", "BMask"),
}


class ConversionError(RuntimeError):
    pass


class Converter:
    def __init__(self, doc: _svg_document.SVGDocument, pcb: pcb.PCB):
        self.doc = doc
        self.pcb = pcb
        self.bbox = (0, 0, 0, 0)
        self.workdir = pathlib.Path(".", ".cache")
        self.workdir.mkdir(parents=True, exist_ok=True)

    @property
    def centroid(self):
        return self.bbox[0] + (self.bbox[2] / 2), self.bbox[1] + (self.bbox[3] / 2)

    def convert(
        self,
        outline: bool = True,
        drills: bool = True,
        layers: bool = True,
        recolor: bool = True,
        cache: bool = True,
        save_layer_images: bool = False,
    ):
        if outline:
            self.convert_outline()
        if drills:
            self.convert_drills()
        if layers:
            self.convert_layers(
                recolor=recolor,
                cache=cache,
                save_layer_images=save_layer_images,
            )

    def convert_outline(self):
        print("[bold]Converting board outline")

        # Find the edgecuts layer
        edge_cuts_layer = []
        for name in _EDGE_LAYERS:
            name = name.replace(".", r"\.")
            edge_cuts_layer.extend(list(self.doc.query_all(f"#{name}")))

        if len(edge_cuts_layer) == 0:
            raise ConversionError("Edge.Cuts layer not found")
        if len(edge_cuts_layer) > 1:
            raise ConversionError("Multiple elements named Edge.Cuts found")

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
            raise ConversionError("No paths found on Edge.Cuts!")

        # Figure out the bounding box (path) of the design so that the offset
        # can be determined. The path with the largest bounding box area is the
        # board bounding box.
        paths.sort(key=lambda p: p[0], reverse=True)

        bounding_area, bounding_brect, _ = paths[0]

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
        self.pcb.add_horizontal_measurement(
            bounding_brect[0],
            bounding_brect[1],
            bounding_brect[0] + bounding_brect[2],
            bounding_brect[1],
        )
        self.pcb.add_vertical_measurement(
            bounding_brect[0],
            bounding_brect[1],
            bounding_brect[0],
            bounding_brect[1] + bounding_brect[3],
        )
        self.pcb.add_rect(
            bounding_brect[0],
            bounding_brect[1],
            bounding_brect[2],
            bounding_brect[3],
            layer="Dwgs.User",
            fill=False,
        )

        # Add all paths as polygons
        for _, _, path in paths:
            for subpath in path.continuous_subpaths():
                points = self.doc.points_to_mm(_geometry.path_to_points(subpath))
                self.pcb.add_poly(points, layer="Edge.Cuts", width=0.5, fill=False)

        return True

    def convert_drills(self):
        print("[bold]Converting drills")

        drill_elms = []
        for name in _DRILL_LAYERS:
            drill_elms.extend(list(self.doc.query_all(f"#{name} *")))

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
            print(
                "[yellow]No drills found[/yellow] [italic](use --no-drills to suppress this warning)"
            )

    def convert_layers(
        self, recolor: bool = True, cache: bool = True, save_layer_images: bool = False
    ):
        # This previously used multiple threads to work around the slowness of
        # having to shell out to bitmap2component, but when we switched to
        # gingerbread.trace the threads no longer saved any time.
        print("[bold]Converting graphic layers")

        for canonical, aliases in _GRAPHIC_LAYERS.items():
            svg_filename = self.workdir / f"{canonical}.svg"
            png_filename = self.workdir / f"{canonical}.png"
            footprint_filename = self.workdir / f"{canonical}.kicad_mod"

            printv(f"Processing {canonical}")

            printv("Preparing SVG for rendering")
            doc = self.doc.copy()

            if not doc.remove_layers(keep=aliases):
                print(f"{canonical:<10} [yellow]not found[/yellow]")
                printv(f"Searched for {', '.join(aliases)}")
                continue

            if recolor:
                doc.recolor()

            svg_text = doc.tostring()

            # See if the cached layer hasn't changed, if so, don't bother re-rendering.
            if (
                cache
                and footprint_filename.exists()
                and compare_file_to_string(svg_filename, svg_text)
            ):
                print(f"{canonical:<10} [cyan]cached[/cyan]")

            # No cached version, render and convert it.
            else:
                if cache:
                    svg_filename.write_text(svg_text)

                surface = doc.render()

                printv("Preparing image for tracing")

                image = trace._load_image(surface)

                if save_layer_images:
                    printv(f"Saving {png_filename}")
                    image.write_to_file(png_filename)

                bitmap = trace._prepare_image(image, invert=False, threshold=127)
                polys = trace._trace_bitmap_to_polys(bitmap, center=False)

                if not polys:
                    print(f"{canonical:<10} [red]empty[red]")
                    continue

                footprint = trace.generate_footprint(
                    polys=polys, dpi=doc.dpi, layer=canonical, position=self.pcb.offset
                )
                footprint_filename.write_text(footprint)

                print(f"{canonical:<10} [green]converted[green]")

            self.pcb.add_literal(footprint_filename.read_text())


def convert(
    *,
    source: pathlib.Path,
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
    recolor: bool = True,
    cache: bool = True,
    save_layer_images: bool = False,
):
    doc = _svg_document.SVGDocument(source, dpi=dpi)
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
    convert.convert(
        outline=outline,
        drills=drills,
        layers=layers,
        cache=cache,
        save_layer_images=save_layer_images,
        recolor=recolor,
    )

    return pcb_


def main():
    parser = argparse.ArgumentParser(
        "convert", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("dest", nargs="?", type=pathlib.Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--time", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--save-layer-images", action="store_true")

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
        "--recolor",
        action=argparse.BooleanOptionalAction,
        default=default_param_value(convert, "recolor"),
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
    set_timing(args.time)

    try:
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
            recolor=args.recolor,
            cache=not args.no_cache,
            save_layer_images=args.save_layer_images,
        )
    except ConversionError as e:
        print(f"[red]Conversion error:[/red] {e}")
        sys.exit(1)

    print("[bold]Writing...")
    with open(args.dest, "w") as fh:
        pcb_.write(fh)

    print(f"[bold][green]Written to {args.dest} :purple_heart:")


if __name__ == "__main__":
    main()
