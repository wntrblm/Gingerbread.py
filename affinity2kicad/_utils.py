# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import argparse
import inspect


def default_param_value(function, name):
    sig = inspect.signature(function)
    params = sig.parameters
    return params[name].default
