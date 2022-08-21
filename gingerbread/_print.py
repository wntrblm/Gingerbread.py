# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import inspect
import pathlib
import sys

import rich.console

_VERBOSE = False
_STDERR_C = rich.console.Console(file=sys.stderr)


def stderr_console() -> rich.console.Console:
    return _STDERR_C


def set_verbose(v: bool):
    global _VERBOSE
    _VERBOSE = v


def print_(*args, **kwargs):
    previous_frame = inspect.currentframe().f_back.f_back
    module = inspect.getmodule(previous_frame.f_code)
    module_name = pathlib.Path(module.__file__).stem

    _STDERR_C.print(f"[italic]{module_name}:[/]", *args, **kwargs)


def print(*args, **kwargs):
    print_(*args, **kwargs)


def printv(*args, **kwargs):
    if _VERBOSE >= 1:
        print_(*args, **kwargs)


def printvv(*args, **kwargs):
    if _VERBOSE >= 2:
        print_(*args, **kwargs)
