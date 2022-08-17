# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import sys
import inspect

import rich.console

_VERBOSE = False
_STDERR_C = rich.console.Console(file=sys.stderr)

def set_verbose(v: bool):
    global _VERBOSE
    _VERBOSE = v


def printv(*args, **kwargs):
    previous_frame = inspect.currentframe().f_back
    module = inspect.getmodule(previous_frame.f_code)
    module_name = module.__name__.rsplit(".").pop()

    if _VERBOSE:
        _STDERR_C.print(f"[italic]{module_name}:[/]", *args, **kwargs)
