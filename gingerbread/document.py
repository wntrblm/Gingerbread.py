# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import math
import re

import cssselect2
from defusedxml import ElementTree

from ._cffi_deps import cairocffi, cairosvg


def _el_get(self, key):
    return self.etree_element.get(key)


def _el_set(self, key, val):
    return self.etree_element.set(key, val)


setattr(cssselect2.ElementWrapper, "get", _el_get)
setattr(cssselect2.ElementWrapper, "set", _el_set)


def _get_matrix_from_transform(transform_string):
    # Adapted from cairosvg
    matrix = cairocffi.Matrix()
    if not transform_string:
        return matrix

    transformations = re.findall(r"(\w+) ?\( ?(.*?) ?\)", transform_string)

    for transformation_type, transformation in transformations:
        values = [float(value) for value in transformation.split(",")]
        if transformation_type == "matrix":
            matrix = cairocffi.Matrix(*values).multiply(matrix)
        else:
            raise ValueError("Unexpected transform type", transformation_type)

    return matrix


def _calculate_total_transform(cssel):
    matrix = cairocffi.Matrix()
    for ancestor in list(reversed(list(cssel.iter_ancestors()))) + [cssel]:
        matrix = (
            _get_matrix_from_transform(ancestor.etree_element.get("transform")) * matrix
        )
    return matrix


def recolor(csstree, parent_id, replacement_style):
    for el in csstree.query_all(f"#{parent_id} *"):
        el.etree_element.set("style", replacement_style)


def vector_diff(x1, y1, x2, y2):
    return (x2 - x1), (y2 - y1)


def vector_length(x, y):
    return math.sqrt((x ** 2 + y ** 2))


class SVGDocument:
    def __init__(self, filename=None, text=None, dpi=2540):
        self.dpi = dpi

        if filename:
            with open(filename, "rb") as fh:
                self.svg_bytes = fh.read()
        else:
            self.svg_bytes = text.encode("utf-8")

        self.etree = ElementTree.XML(self.svg_bytes)
        self.csstree = cssselect2.ElementWrapper.from_xml_root(self.etree)

    def copy(self):
        return SVGDocument(text=self.tostring(), dpi=self.dpi)

    @property
    def dpmm(self):
        return 25.4 / self.dpi

    def to_mm(self, val, places=2):
        if not isinstance(val, float):
            val = float(val)
        return round(val * self.dpmm, places)

    def query_all(self, selector):
        for item in self.csstree.query_all(selector):
            yield self._wrap(item)

    def _wrap(self, cssel):
        cssel.matrix = self.transform(cssel)
        self._localize(cssel)
        return cssel

    def _localize(self, el):
        if "circle" in el.etree_element.tag:
            local_r = float(el.get("r"))
            local_cx = float(el.get("cx"))
            local_cy = float(el.get("cy"))

            screen_x, screen_y = el.matrix.transform_point(local_cx, local_cy)
            screen_x2, screen_y2 = el.matrix.transform_point(
                local_cx + local_r, local_cy
            )
            screen_r = vector_length(
                *vector_diff(screen_x, screen_y, screen_x2, screen_y2)
            )

            el.set("screen_cx", str(screen_x))
            el.set("screen_cy", str(screen_y))
            el.set("screen_r", str(screen_r))
            return

        if "rect" in el.etree_element.tag:
            local_x = float(el.get("x"))
            local_y = float(el.get("y"))
            local_width = float(el.get("width"))
            local_height = float(el.get("height"))

            screen_x, screen_y = el.matrix.transform_point(local_x, local_y)
            screen_x2, screen_y2 = el.matrix.transform_point(
                local_x + local_width, local_y + local_height
            )
            screen_width, screen_height = vector_diff(
                screen_x, screen_y, screen_x2, screen_y2
            )

            el.set("screen_x", str(screen_x))
            el.set("screen_y", str(screen_y))
            el.set("screen_width", str(screen_width))
            el.set("screen_height", str(screen_height))
            return

    def remove_layers(self, keep=None):
        keep = keep or []
        found = False

        for node in list(self.etree):
            if node.attrib.get("id", "") in keep:
                node.attrib["visibility"] = "visible"
                found = True
                continue

            # Check if this is a group with the layer as its single child.
            elif (
                node.tag == "{http://www.w3.org/2000/svg}g"
                and node.attrib.get("id", None) is None
            ):
                children = list(node)
                if children and children[0].attrib.get("id", "") in keep:
                    node.attrib["visibility"] = "visible"
                    found = True
                    continue

            self.etree.remove(node)

        return found

    def transform(self, cssel):
        return _calculate_total_transform(cssel)

    def recolor(self, id, replacement_style="fill:black;"):
        recolor(self.csstree, id, replacement_style)

    def tobytestring(self):
        return ElementTree.tostring(self.etree)

    def tostring(self):
        return ElementTree.tostring(self.etree, encoding="unicode")

    def render(self, dst):
        tree = cairosvg.parser.Tree(bytestring=self.tostring())
        surface = cairosvg.surface.PNGSurface(tree, output=None, dpi=self.dpi)

        with open(dst, "wb") as fh:
            surface.cairo.write_to_png(fh)

        return dst
