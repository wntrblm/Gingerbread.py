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
import pathlib
import sys
from typing import Generator, Union

import gdstk
import numpy as np
import potracecffi
import pyvips
import rich

from . import _sexpr as s
from ._cffi_deps import cairocffi
from ._geometry import bezier_to_points
from ._print import printv, set_verbose


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


def _load_image(path_surface_or_image) -> pyvips.Image:
    if isinstance(path_surface_or_image, (str, pathlib.Path)):
        printv(f"Loading {path_surface_or_image}")
        return pyvips.Image.new_from_file(path_surface_or_image)

    if isinstance(path_surface_or_image, cairocffi.ImageSurface):
        printv("Loading image from cairo surface")
        # Note: currently this messes up the channel order, since vips is expecting
        # rgba and cairo gives us pre-multiplied bgra. See
        # https://github.com/libvips/libvips/blob/master/libvips/foreign/cairo.c
        # This isn't too much of a concern, as the image gets thresholded down to
        # to black and white so the pixel order doesn't really matter.
        path_surface_or_image.flush()
        surface_data = np.ndarray(
            shape=(
                path_surface_or_image.get_height(),
                path_surface_or_image.get_width(),
                4,
            ),
            dtype=np.uint8,
            buffer=path_surface_or_image.get_data(),
        )
        return pyvips.Image.new_from_array(surface_data, interpretation="srgb")

    else:
        raise ValueError(
            f"{path_surface_or_image} is a {type(path_surface_or_image).__name__} not a filesystem path, a vips.Image, or a cairo.Surface"
        )


def _prepare_image(
    image: pyvips.Image, invert: bool = False, threshold: int = 127
) -> np.array:
    printv(
        f"Image size: {image.width} x {image.height}, {image.bands} bands, {image.interpretation}"
    )
    printv("Converting to black & white")

    if image.hasalpha():
        image = image.flatten(background=[255, 255, 255])

    image = image.colourspace("b-w")
    image_array = image.numpy()

    printv(f"Applying {threshold=}")
    image_array = np.where(image_array > threshold, invert, not invert)

    return image_array


def _trace_result_to_polys(
    trace_result, offset: tuple[float, float], bezier_resolution: float = 0.25
):
    # First, go through all the paths and generate a main polygon and a list of
    # hole polygons for each.
    polys_and_holes = []

    for path in potracecffi.iter_paths(trace_result):
        pts = [
            (p[0] + offset[0], p[1] + offset[1])
            for p in _path_to_poly_pts(path, bezier_resolution=bezier_resolution)
        ]

        hole = path.sign == ord("-")
        poly = gdstk.Polygon(list(pts))

        if not hole:
            polys_and_holes.append([poly])
        else:
            polys_and_holes[-1].append(poly)

    # Second, iterate through the list of polygons and holes and boolean
    # subtract all the holes. This is much faster than running the boolean op
    # seperately for each hole.
    polys = []
    for poly, *holes in polys_and_holes:
        if not holes:
            polys.append(poly)
            continue

        results = gdstk.boolean(poly, holes, "not")

        polys.extend(results)

    return polys


def _trace_bitmap_to_polys(
    bitmap: np.array, center: bool = True, bezier_resolution=0.25
) -> list[gdstk.Polygon]:

    if center:
        offset = (-bitmap.shape[1] / 2, -bitmap.shape[0] / 2)
    else:
        offset = (0, 0)

    printv("Tracing")
    trace_result = potracecffi.trace(bitmap, turdsize=0)

    printv("Converting paths to polygons")
    polys = _trace_result_to_polys(
        trace_result, offset=offset, bezier_resolution=bezier_resolution
    )

    printv(f"Converted to {len(polys)} polygons")

    return polys


def _generate_fp_poly(poly: gdstk.Polygon, *, layer: str, dpmm: float) -> s.S:
    pts = ((pt[0] * dpmm, pt[1] * dpmm) for pt in poly.points)

    return s.fp_poly(pts=pts, layer=layer, width=0, fill=True)


def generate_footprint(
    polys: list[gdstk.Polygon],
    *,
    dpi: float,
    layer: str,
    position: tuple[float, float] = (0, 0),
) -> str:
    printv(f"Generating footprint, {dpi=}")
    dpmm = 25.4 / dpi

    return str(
        s.footprint(
            "Graphics",
            at=position,
            *(_generate_fp_poly(poly, layer=layer, dpmm=dpmm) for poly in polys),
            layer=layer,
        )
    )


def trace(
    image: Union[pathlib.Path, pyvips.Image, cairocffi.ImageSurface],
    *,
    invert: bool = False,
    threshold: int = 127,
    dpi: float = 2540,
    layer: str = "F.SilkS",
    center: bool = True,
    bezier_resolution: float = 0.25,
    position: tuple[float, float] = (0, 0),
):
    vips_image = _load_image(image)
    bitmap = _prepare_image(vips_image, invert=invert, threshold=threshold)
    polys = _trace_bitmap_to_polys(
        bitmap, center=center, bezier_resolution=bezier_resolution
    )
    fp = generate_footprint(polys=polys, dpi=dpi, layer=layer, position=position)
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

    try:
        pyperclip.copy(fp)
        rich.print("[green]Copied to clipboard! :purple_heart:", file=sys.stderr)
    except pyperclip.PyperclipException:
        out_file = args.image.with_suffix(".kicad_mod")
        rich.print(f"[yellow]Unable to copy to clipboard, saving as {out_file}")
        out_file.write_text(fp)


if __name__ == "__main__":
    main()
