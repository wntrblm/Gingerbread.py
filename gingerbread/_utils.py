# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import math
import inspect
import numpy as np


def default_param_value(function, name):
    sig = inspect.signature(function)
    params = sig.parameters
    return params[name].default


# Ported from https://gitlab.com/kicad/code/kicad/-/blob/2ee65b2d83923acb71aa77ce0efab09a3f2a8f44/bitmap2component/bitmap2component.cpp#L544
def bezier_to_points(p1, p2, p3, p4, delta=0.25):
    # Approximate the curve by small line segments. The interval
    # size, epsilon, is determined on the fly so that the distance
    # between the true curve and its approximation does not exceed the
    # desired accuracy delta.

    # dd = maximal value of 2nd derivative over curve - this must occur at an endpoint.
    dd0 = math.pow(p1[0] - 2 * p2[0] + p3[0], 2) + math.pow(
        p1[1] - 2 * p2[1] + p3[1], 2
    )
    dd1 = math.pow(p2[0] - 2 * p3[0] + p4[0], 2) + math.pow(
        p2[1] - 2 * p3[1] + p4[1], 2
    )
    dd = 6 * math.sqrt(max(dd0, dd1))
    e2 = 8 * delta / dd if 8 * delta <= dd else 1
    interval = math.sqrt(e2)

    for t in np.arange(0, 1, interval):
        x = (
            p1[0] * math.pow(1 - t, 3)
            + 3 * p2[0] * math.pow(1 - t, 2) * t
            + 3 * p3[0] * (1 - t) * math.pow(t, 2)
            + p4[0] * math.pow(t, 3)
        )
        y = (
            p1[1] * math.pow(1 - t, 3)
            + 3 * p2[1] * math.pow(1 - t, 2) * t
            + 3 * p3[1] * (1 - t) * math.pow(t, 2)
            + p4[1] * math.pow(t, 3)
        )
        yield (x, y)

    yield p4
