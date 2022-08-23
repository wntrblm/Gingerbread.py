# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import re
import time

import cssselect2
from defusedxml import ElementTree

from ._cffi_deps import cairocffi, cairosvg
from ._print import printv


# Monkeypatches cssselect2.ElementWrapper to add get and set methods.
def _el_get(self, key, default=None):
    return self.etree_element.get(key, default)


def _el_set(self, key, val):
    return self.etree_element.set(key, val)


setattr(cssselect2.ElementWrapper, "get", _el_get)
setattr(cssselect2.ElementWrapper, "set", _el_set)


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

    def iter_to_mm(self, vals, places=2):
        for val in vals:
            yield self.to_mm(val, places=places)

    def points_to_mm(self, pts, places=2):
        for pt in pts:
            yield (self.to_mm(pt[0], places=places), self.to_mm(pt[1], places=places))

    def query_all(self, selector):
        yield from self.csstree.query_all(selector)

    def remove_layers(self, keep=None):
        keep = keep or []
        keep_found = False
        count = 0

        for node in list(self.etree):
            if node.attrib.get("id", "") in keep:
                node.attrib["visibility"] = "visible"
                keep_found = True
                continue

            # Check if this is a group with the layer as its single child.
            elif (
                node.tag == "{http://www.w3.org/2000/svg}g"
                and node.attrib.get("id", None) is None
            ):
                children = list(node)
                if children and children[0].attrib.get("id", "") in keep:
                    node.attrib["visibility"] = "visible"
                    keep_found = True
                    continue

            self.etree.remove(node)
            count += 1

        printv(f"Removed {count} layers, keeping {keep}")

        return keep_found

    def recolor(self, fill="black", stroke="black"):
        count = 0

        for el in self.csstree.query_all("[style]"):
            style = el.get("style")
            style = re.sub(r"fill:[^none](.+?);", f"fill:{fill};", style)
            style = re.sub(r"stroke:[^none](.+?);", f"stroke:{fill};", style)
            el.set("style", style)
            count += 1

        printv(f"Recolored {count} elements")

    def tobytestring(self):
        return ElementTree.tostring(self.etree)

    def tostring(self):
        return ElementTree.tostring(self.etree, encoding="unicode")

    def render(self) -> cairocffi.Surface:
        printv(f"Rendering SVG dpi={self.dpi}")
        start_time = time.perf_counter()

        tree = cairosvg.parser.Tree(bytestring=self.tostring())

        surface = cairosvg.surface.PNGSurface(tree, output=None, dpi=self.dpi)
        surface.cairo.flush()

        delta = time.perf_counter() - start_time
        printv(f"Rendering took {delta:0.2f} s")

        return surface.cairo
