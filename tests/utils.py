# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import pathlib
import re

RESOURCES = pathlib.Path(__file__).parent / "resources"


def _remove_timestamps(val: str) -> str:
    val = re.sub(r"\(tstamp \".+?\"\)", '(tstamp "*")', val)
    val = re.sub(r"\(tedit \".+?\"\)", '(tedit "*")', val)
    return val


def compare_footprints(ref: pathlib.Path, res: str) -> bool:
    ref_text = _remove_timestamps(ref.read_text()).strip()
    res_text = _remove_timestamps(res).strip()

    return ref_text == res_text
