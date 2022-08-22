# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

# Fixes loading homebrew libraries when using pyenv on macos
# https://github.com/Homebrew/discussions/discussions/3424
# https://github.com/Homebrew/homebrew-core/blob/ed6d3f73a6cd3d779d0254f4ae5ba39b99d3217b/Formula/python@3.10.rb#L185-L192

import sys

if sys.platform == "darwin":
    import ctypes.macholib.dyld

    ctypes.macholib.dyld.DEFAULT_LIBRARY_FALLBACK.append("/opt/homebrew/lib")

import cairocffi
import cairosvg
import pangocairocffi
import pangocffi

__all__ = [
    "cairocffi",
    "pangocffi",
    "pangocairocffi",
    "cairosvg",
]
