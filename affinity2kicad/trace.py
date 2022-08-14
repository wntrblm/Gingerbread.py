# https://gitlab.com/kicad/code/kicad/-/blob/master/bitmap2component/bitmap2component.cpp
# https://gitlab.com/kicad/code/kicad/-/blob/master/libs/kimath/include/geometry/shape_poly_set.h
# https://gitlab.com/kicad/code/kicad/-/blob/master/libs/kimath/src/geometry/shape_poly_set.cpp
# https://heitzmann.github.io/gdstk/geometry/gdstk.Polygon.html#gdstk.Polygon
# http://potrace.sourceforge.net/potracelib.pdf

import argparse
import io
import math
import pathlib
import sys
import uuid

import gdstk
import numpy as np
import PIL.Image
import PIL.ImageOps
import potrace
import svgpathtools
from rich import print


def printe(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def bezier_to_points(seg, points=5):
    num_lines = int(math.ceil(seg.length() / points))
    pts = [seg.point(t) for t in np.linspace(0, 1, num_lines + 1)]
    return pts


def path_to_poly_pts(path):
    pts = [path.start_point]
    for segment in path:
        if isinstance(segment, potrace.CornerSegment):
            pts.append(segment.c)
            pts.append(segment.end_point)
        elif isinstance(segment, potrace.BezierSegment):
            b = svgpathtools.CubicBezier(
                complex(*pts[-1]),
                complex(*segment.c1),
                complex(*segment.c2),
                complex(*segment.end_point),
            )
            for pt in bezier_to_points(b):
                pts.append((pt.real, pt.imag))
    return pts


def load_image(path):
    printe(f"Loading {path}")
    PIL.Image.MAX_IMAGE_PIXELS = 2**28
    image = PIL.Image.open(path)
    return image


def image_to_potrace_bitmap(
    image: PIL.Image, invert: bool = False, threshold: int = 127
) -> potrace.Bitmap:
    printe("Converting to black & white")
    image = PIL.ImageOps.grayscale(image)
    image_array = np.array(image)
    image_array = np.vectorize(lambda x: (not invert) if x < threshold else invert)(
        image_array
    )
    printe("Loading bitmap into potrace")
    return potrace.Bitmap(image_array)


def trace_to_polys(bitmap: potrace.Bitmap) -> list:
    printe("Tracing...")
    paths = bitmap.trace(turdsize=0)
    printe(f"Traced {len(paths)} paths")

    polys = []

    for path in paths:
        pts = path_to_poly_pts(path.curves[0])
        hole = path.sign == ord("-")

        if not hole:
            p = gdstk.Polygon(pts)
            # printe(f"Poly {p.size} {p=}")
            polys.append(p)
        else:
            hole = gdstk.Polygon(pts)
            result = gdstk.boolean(polys.pop(), hole, "not")
            # printe(f"Hole {hole.size} {hole=} {result=}")
            polys.extend(result)

    printe(f"Generated {len(polys)} polygons")

    return polys


def generate_poly(poly: list[list[int, int]], layer: str, dpmm: float) -> str:
    output = io.StringIO()

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

    return output.getvalue()


def generate_footprint(polys: list, dpi: float = 2540, layer: str = "F.SilkS") -> str:
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
        print(generate_poly(poly, layer=layer, dpmm=dpmm), file=output)

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
    bitmap = image_to_potrace_bitmap(
        image, invert=args.invert, threshold=args.threshold
    )
    polys = trace_to_polys(bitmap)
    fp = generate_footprint(polys=polys, dpi=args.dpi, layer=args.layer)

    pyperclip.copy(fp)

    print("[green]Copied to clipboard!")


if __name__ == "__main__":
    main()
