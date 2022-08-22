# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import inspect
import pathlib
import sys
import threading
import time

import rich.console

_thread_local = threading.local()

_VERBOSE = False
_TIMING = False


def stderr_console() -> rich.console.Console:
    if not hasattr(_thread_local, "stderr_c"):
        _thread_local.stderr_c = rich.console.Console(file=sys.stderr)
    return _thread_local.stderr_c


def set_verbose(v: bool):
    global _VERBOSE
    _VERBOSE = v


def set_timing(t: bool):
    global _TIMING
    _TIMING = t


def print_(*args, **kwargs):
    previous_frame = inspect.currentframe().f_back.f_back
    module = inspect.getmodule(previous_frame.f_code)

    if module is None:
        module_name = "unknown"
    else:
        module_name = pathlib.Path(module.__file__).stem.lstrip("_")

    if _TIMING:
        timestr = f"{time.process_time():5.3f}"
        stderr_console().print(
            f"[italic]{timestr:>8} {module_name}:[/]", *args, **kwargs
        )
    else:
        stderr_console().print(f"[italic]{module_name}:[/]", *args, **kwargs)


def print(*args, **kwargs):
    print_(*args, **kwargs)


def printv(*args, **kwargs):
    global _VERBOSE
    if _VERBOSE >= 1:
        print_(*args, **kwargs)


def printvv(*args, **kwargs):
    global _VERBOSE
    if _VERBOSE >= 2:
        print_(*args, **kwargs)
