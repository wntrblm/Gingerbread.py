# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT


import inspect
import pathlib


def default_param_value(function, name):
    sig = inspect.signature(function)
    params = sig.parameters
    return params[name].default


def compare_file_to_string(filename: pathlib.Path, contents: str) -> bool:
    if not filename.exists():
        return False

    with open(filename, "r") as fh:
        file_contents = fh.read()

    return contents == file_contents
