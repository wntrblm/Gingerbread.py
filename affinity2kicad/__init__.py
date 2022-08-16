# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

"""Winterbloom's tooling for converting Affinity Designer SVG files to KiCAD PCB files."""

from .converter import Converter
from .document import SVGDocument
from .pcbnew import PCB
from . import helpers

__version__ = "0.0.0.dev0"
__all__ = ["Converter", "helpers", "SVGDocument", "PCB"]


def convert(*, source, title, rev):
    doc = SVGDocument(source)
    pcb = PCB(title=title, rev=rev)

    converter = Converter(doc, pcb)
    converter.convert()

    return pcb
