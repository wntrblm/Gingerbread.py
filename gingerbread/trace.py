# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

# https://gitlab.com/kicad/code/kicad/-/blob/master/bitmap2component/bitmap2component.cpp
# https://gitlab.com/kicad/code/kicad/-/blob/master/libs/kimath/include/geometry/shape_poly_set.h
# https://gitlab.com/kicad/code/kicad/-/blob/master/libs/kimath/src/geometry/shape_poly_set.cpp
# https://heitzmann.github.io/gdstk/geometry/gdstk.Polygon.html#gdstk.Polygon
# http://potrace.sourceforge.net/potracelib.pdf
# https://www.libvips.org/API/current/


import argparse
import io
import pathlib
import sys
from typing import Generator

import gdstk
import numpy as np
import potracecffi
import pyvips
import rich

from . import sexpr as s
from ._print import set_verbose, printv
from ._utils import bezier_to_points


def _path_to_poly_pts(
    path, bezier_resolution=0.25
) -> Generator[tuple[float, float], None, None]:
    last = potracecffi.curve_start_point(path.curve)
    yield last

    for segment in potracecffi.iter_curve(path.curve):
        if segment.tag == potracecffi.CORNER:
            yield segment.c1
            yield segment.c2
        elif segment.tag == potracecffi.CURVETO:
            yield from bezier_to_points(
                last, segment.c0, segment.c1, segment.c2, delta=bezier_resolution
            )

        last = segment.c2


def _load_image(path) -> pyvips.Image:
    printv(f"Loading {path}")
    image = pyvips.Image.new_from_file(path)
    return image


def _prepare_image(
    image: pyvips.Image, invert: bool = False, threshold: int = 127
) -> np.array:
    printv(f"Image size: {image.width} x {image.height}")
    printv("Converting to black & white")

    if image.hasalpha():
        image = image.flatten(background=[255, 255, 255])

    image = image.colourspace("b-w")
    image_array = image.numpy()

    printv(f"Applying {threshold=}")
    image_array = np.where(image_array > threshold, invert, not invert)

    return image_array


def _trace_bitmap_to_polys(
    bitmap: np.array, center: bool = True, bezier_resolution=0.25
) -> list[gdstk.Polygon]:
    printv("Tracing")
    trace_result = potracecffi.trace(bitmap, turdsize=0)

    printv("Converting paths to polygons")

    if center:
        offset = (-bitmap.shape[1] / 2, -bitmap.shape[0] / 2)
    else:
        offset = (0, 0)

    polys = []

    for path in potracecffi.iter_paths(trace_result):
        pts = [
            (p[0] + offset[0], p[1] + offset[1])
            for p in _path_to_poly_pts(path, bezier_resolution=bezier_resolution)
        ]
        hole = path.sign == ord("-")

        if not hole:
            p = gdstk.Polygon(list(pts))
            polys.append(p)
        else:
            hole_poly = gdstk.Polygon(list(pts))
            result = gdstk.boolean(polys.pop(), hole_poly, "not")

            # if gdstk produced multiple polygons, stitch them back together
            while len(result) > 1:
                new_result = gdstk.boolean(result[0], result[1], "or")
                result = new_result + result[2:]

            polys.extend(result)

    printv(f"Converted to {len(polys)} polygons")

    return polys


def _generate_fp_poly(poly: gdstk.Polygon, *, layer: str, dpmm: float) -> s.S:
    pts = s.pts(*(s.xy(pt[0] * dpmm, pt[1] * dpmm) for pt in poly.points))

    return s.fp_poly(pts=pts, layer=layer, width=0, fill=True)


def generate_footprint(polys: list[gdstk.Polygon], *, dpi: float, layer: str) -> str:
    printv(f"Generating footprint, {dpi=}")
    dpmm = 25.4 / dpi

    return str(
        s.footprint(
            "Graphics",
            *(_generate_fp_poly(poly, layer=layer, dpmm=dpmm) for poly in polys),
            layer=layer,
        )
    )


def trace(
    image_path: pathlib.Path,
    *,
    invert: bool = False,
    threshold: int = 127,
    dpi: float = 2540,
    layer: str = "F.SilkS",
    center: bool = True,
    bezier_resolution=0.25,
):
    image = _load_image(image_path)
    bitmap = _prepare_image(image, invert=invert, threshold=threshold)
    polys = _trace_bitmap_to_polys(
        bitmap, center=center, bezier_resolution=bezier_resolution
    )
    fp = generate_footprint(polys=polys, dpi=dpi, layer=layer)
    return fp


def main():
    import pyperclip

    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=pathlib.Path)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--dpi", type=float, default=2540)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--threshold", type=int, default=127)
    parser.add_argument("--bezier-resolution", type=float, default=0.25)
    parser.add_argument(
        "--layer",
        choices=[
            "F.SilkS",
            "B.SilkS",
            "F.Cu",
            "B.Cu",
            "B.Mask",
            "F.Mask",
            "User.Drawings",
            "User.Comments",
        ],
        default="F.SilkS",
    )

    args = parser.parse_args()

    set_verbose(args.verbose)

    fp = trace(
        args.image,
        invert=args.invert,
        threshold=args.threshold,
        dpi=args.dpi,
        layer=args.layer,
        bezier_resolution=args.bezier_resolution,
    )

    pyperclip.copy(fp)

    rich.print("[green]Copied to clipboard! :purple_heart:", file=sys.stderr)


if __name__ == "__main__":
    main()
