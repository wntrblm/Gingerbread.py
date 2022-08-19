# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

"""
Gingerbread is a set of Python utilities used by Winterbloom
(https://winterbloom.com) to create decorative printed circuit boards (PCBs).
"""

from os import PathLike
from . import helpers

__version__ = "0.0.0.dev0"
__all__ = ["convert", "helpers"]


def convert(*, source: PathLike, title: str, rev: str):
    from .converter import Converter
    from .document import SVGDocument
    from .pcb import PCB

    doc = SVGDocument(source)
    pcb = PCB(title=title, rev=rev)

    converter = Converter(doc, pcb)
    converter.convert()

    return pcb
