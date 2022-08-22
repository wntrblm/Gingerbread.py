# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

"""Helpers for manipulating, processing, and converting geometry"""

import math
from typing import Iterator

import cssselect2
import numpy as np
import svgpathtools


def bbox_to_rect(xmin, xmax, ymin, ymax) -> tuple[float, float, float, float]:
    return xmin, ymin, xmax - xmin, ymax - ymin


def svg_elements_to_paths(
    svg_elements: Iterator[cssselect2.ElementWrapper],
) -> Iterator[tuple[cssselect2.ElementWrapper, svgpathtools.Path]]:
    """Converts a list of SVG shape elements to paths."""

    # Based on svgpathtools.svg2paths
    for elem in svg_elements:
        match elem.local_name:
            case "rect":
                yield elem, svgpathtools.parse_path(
                    svgpathtools.svg_to_paths.rect2pathd(elem)
                )
            case "polygon":
                yield elem, svgpathtools.parse_path(
                    svgpathtools.svg_to_paths.polygon2pathd(elem)
                )
            case "circle" | "ellipse":
                yield elem, svgpathtools.parse_path(
                    svgpathtools.svg_to_paths.ellipse2pathd(elem)
                )
            case "path":
                yield elem, svgpathtools.parse_path(elem.get("d"))
            case "g":
                yield from svg_elements_to_paths(elem.iter_children())
            case _:
                yield elem, None


def path_to_points(
    path: svgpathtools.Path, delta: float = 1
) -> Iterator[tuple[float, float]]:
    """Converts an SVG path to a series of points approximating that path"""
    for seg in path:
        if isinstance(seg, svgpathtools.Line):
            yield (seg.start.real, seg.start.imag)
            yield (seg.end.real, seg.end.imag)

        elif isinstance(seg, svgpathtools.CubicBezier):
            yield from bezier_to_points(
                (seg.start.real, seg.start.imag),
                (seg.control1.real, seg.control1.imag),
                (seg.control2.real, seg.control2.imag),
                (seg.end.real, seg.end.imag),
                delta=delta,
            )

        else:
            raise ValueError(f"Can't convert path segment {seg=}.")


# Ported from https://gitlab.com/kicad/code/kicad/-/blob/2ee65b2d83923acb71aa77ce0efab09a3f2a8f44/bitmap2component/bitmap2component.cpp#L544
def bezier_to_points(p1, p2, p3, p4, delta=0.25):
    """Approximates a quadratic bezier curve as a series of points"""
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
