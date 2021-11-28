# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

"""Winterbloom's tooling for converting Affinity Designer SVG files to KiCAD PCB files."""

from .converter import Converter
from .document import SVGDocument
from .pcbnew import PCB
from .fancytext import FancyText
from . import helpers

__version__ = "0.0.0.dev0"
__all__ = ["Converter", "helpers", "SVGDocument", "PCB", "FancyText"]
