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
import math
import pathlib
import sys
from typing import Generator
import uuid

import gdstk
import numpy as np
import potracecffi
import pyvips
from rich import print


def printe(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# Ported from https://gitlab.com/kicad/code/kicad/-/blob/2ee65b2d83923acb71aa77ce0efab09a3f2a8f44/bitmap2component/bitmap2component.cpp#L544
def bezier_to_points(p1, p2, p3, p4, delta=0.25):
    # Approximate the curve by small line segments. The interval
    # size, epsilon, is determined on the fly so that the distance
    # between the true curve and its approximation does not exceed the
    # desired accuracy delta.

    # dd = maximal value of 2nd derivative over curve - this must occur at an endpoint.
    dd0 = math.pow(p1[0] - 2 * p2[0] + p3[0], 2) + math.pow(
        p1[1] - 2 * p2[1] + p3[1], 2
    )
    dd1 = math.pow(p2[0] - 2 * p3[0] + p4[0], 2) + math.pow(
        p2[1] - 2 * p3[1] + p4[1], 2
    )
    dd = 6 * math.sqrt(max(dd0, dd1))
    e2 = 8 * delta / dd if 8 * delta <= dd else 1
    interval = math.sqrt(e2)

    for t in np.arange(0, 1, interval):
        x = (
            p1[0] * math.pow(1 - t, 3)
            + 3 * p2[0] * math.pow(1 - t, 2) * t
            + 3 * p3[0] * (1 - t) * math.pow(t, 2)
            + p4[0] * math.pow(t, 3)
        )
        y = (
            p1[1] * math.pow(1 - t, 3)
            + 3 * p2[1] * math.pow(1 - t, 2) * t
            + 3 * p3[1] * (1 - t) * math.pow(t, 2)
            + p4[1] * math.pow(t, 3)
        )
        yield (x, y)

    yield p4


def path_to_poly_pts(path) -> Generator[tuple[float, float], None, None]:
    last = potracecffi.curve_start_point(path.curve)
    yield last

    for segment in potracecffi.iter_curve(path.curve):
        if segment.tag == potracecffi.CORNER:
            yield segment.c1
            yield segment.c2
        elif segment.tag == potracecffi.CURVETO:
            yield from bezier_to_points(last, segment.c0, segment.c1, segment.c2)

        last = segment.c2


def load_image(path):
    printe(f"Loading {path}")
    image = pyvips.Image.new_from_file(path)
    return image


def prepare_image(
    image: pyvips.Image, invert: bool = False, threshold: int = 127
) -> np.array:
    printe(f"Image size: {image.width} x {image.height}")
    printe("Converting to black & white")

    if image.hasalpha():
        image = image.flatten()

    image = image.colourspace("b-w")
    image_array = image.numpy()

    printe(f"Applying {threshold=}")
    image_array = np.where(image_array > threshold, invert, not invert)

    return image_array


def trace_to_polys(bitmap: np.array) -> list:
    printe("Tracing")
    trace_result = potracecffi.trace(bitmap, turdsize=0)

    printe("Converting paths to polygons")
    polys = []

    for path in potracecffi.iter_paths(trace_result):
        pts = path_to_poly_pts(path)
        hole = path.sign == ord("-")

        if not hole:
            p = gdstk.Polygon(list(pts))
            # printe(f"Poly {p.size} {p=}")
            polys.append(p)
        else:
            hole = gdstk.Polygon(list(pts))
            result = gdstk.boolean(polys.pop(), hole, "not")
            # printe(f"Hole {hole.size} {hole=} {result=}")
            polys.extend(result)

    printe(f"Converted to {len(polys)} polygons")

    return polys


def generate_poly(poly: list[list[int, int]], layer: str, dpmm: float, output) -> str:
    print("  (fp_poly\n    (pts ", file=output)

    for pt in poly.points:
        print(f"      (xy {pt[0] * dpmm} {pt[1] * dpmm})", file=output)

    print(
        f"     )\n"
        f'    (layer "{layer}")\n'
        f"    (fill solid)\n"
        f"    (width 0)\n"
        f'    (tstamp "{uuid.uuid4()}")\n'
        f"  )\n",
        file=output,
    )


def generate_footprint(polys: list, dpi: float = 2540, layer: str = "F.SilkS") -> str:
    printe(f"Generating footprint, {dpi=}")
    dpmm = 25.4 / dpi
    output = io.StringIO()

    print(
        f'(footprint "TEST"'
        f"  (version 20220101)"
        f'  (generator "affinity2kicad")'
        f'  (layer "F.SilkS")'
        f'  (tedit "{uuid.uuid1()}")'
        f"  (at 0 0)",
        file=output,
    )

    for poly in polys:
        generate_poly(poly, layer=layer, dpmm=dpmm, output=output)

    print(")", file=output)

    return output.getvalue()


def main():
    import pyperclip

    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=pathlib.Path)
    parser.add_argument("--dpi", type=float, default=2540)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--threshold", type=int, default=127)
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

    image = load_image(args.image)
    bitmap = prepare_image(image, invert=args.invert, threshold=args.threshold)
    polys = trace_to_polys(bitmap)
    fp = generate_footprint(polys=polys, dpi=args.dpi, layer=args.layer)

    pyperclip.copy(fp)

    print("[green]Copied to clipboard!")


if __name__ == "__main__":
    main()
