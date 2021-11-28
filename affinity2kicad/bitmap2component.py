# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import subprocess


def bitmap2component(src, dst, layer, invert, dpi):
    return subprocess.run(
        [
            "bitmap2component_osx",
            src,
            dst,
            layer,
            str(invert).lower(),
            str(dpi),
        ],
        capture_output=True,
        check=True,
    )
