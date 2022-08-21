# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import cssselect2
from defusedxml import ElementTree

from ._cffi_deps import cairosvg


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

    def recolor(self, id, replacement_style="fill:black;"):
        for el in self.csstree.query_all(f"#{id} *"):
            el.etree_element.set("style", replacement_style)

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
