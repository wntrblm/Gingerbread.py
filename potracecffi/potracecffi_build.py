# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import pathlib

from cffi import FFI

HERE = pathlib.Path(__file__).parent
ffibuilder = FFI()

ffibuilder.set_source(
    "_potracecffi",
    (HERE / "potracecffi.c").read_text(),
    libraries=["potrace"],
    include_dirs=["/opt/homebrew/opt/potrace/include"],
    library_dirs=["/opt/homebrew/opt/potrace/lib"],
)

ffibuilder.cdef(
    (HERE / "potracecffi.h").read_text())


if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
