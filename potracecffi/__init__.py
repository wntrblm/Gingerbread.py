# https://cffi.readthedocs.io/en/latest/using.html#working-with-pointers-structures-and-arrays

import dataclasses

from ._potracecffi import ffi, lib

CURVETO = 1
CORNER = 2
TURNPOLICY_BLACK = 0
TURNPOLICY_WHITE = 1
TURNPOLICY_LEFT = 2
TURNPOLICY_RIGHT = 3
TURNPOLICY_MINORITY = 4
TURNPOLICY_MAJORITY = 5
TURNPOLICY_RANDOM = 6


def version():
    return ffi.string(lib.potrace_version()).decode("utf-8")


def iter_paths(plist_or_state):
    if ffi.typeof(plist_or_state) == ffi.typeof("struct potrace_state_s *"):
        plist = plist_or_state.plist
    else:
        plist = plist_or_state

    while plist != ffi.NULL:
        yield plist
        plist = plist.next


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Curve:
    tag: int
    c0: tuple[float, float]
    c1: tuple[float, float]
    c2: tuple[float, float]


def iter_curve(curve):
    for n in range(curve.n):
        yield Curve(
            tag=curve.tag[n],
            c0=(curve.c[n][0].x, curve.c[n][0].y),
            c1=(curve.c[n][1].x, curve.c[n][1].y),
            c2=(curve.c[n][2].x, curve.c[n][2].y),
        )


def curve_start_point(curve):
    p = curve.c[curve.n - 1][2]
    return (p.x, p.y)


def _get_state_size(state):
    # TODO: This doesn't account for priv fields and should probably be
    # done in C
    size = ffi.sizeof(state)
    for p in iter_paths(state.plist):
        size += ffi.sizeof(p)
        size += ffi.sizeof("int") * p.curve.n
        size += ffi.sizeof("potrace_dpoint_t") * 3 * p.curve.n

    return size


def trace(
    image,
    turdsize: int = 2,
    turnpolicy: int = TURNPOLICY_MINORITY,
    alphamax: float = 1.0,
    opticurve: int = 1,
    opttolerance: float = 0.2,
):
    params = ffi.NULL
    bm = ffi.NULL

    try:
        params = lib.potrace_param_default()
        params.turdsize = turdsize
        params.turnpolicy = turnpolicy
        params.alphamax = alphamax
        params.opticurve = opticurve
        params.opttolerance = opttolerance

        bm = ffi.new("potrace_bitmap_t*")

        result = lib.potracecffi_pack_bitmap_data(
            bm, ffi.from_buffer(image), image.shape[1], image.shape[0]
        )

        if result != 0:
            raise RuntimeError("Failed to pack bitmap data")

        state = lib.potrace_trace(params, bm)

        if state.status != 0:
            raise RuntimeError("Trace failed")

        return ffi.gc(state, lib.potrace_state_free, _get_state_size(state))

    finally:
        lib.potrace_param_free(params)
        lib.potracecffi_free_bitmap_data(bm)
