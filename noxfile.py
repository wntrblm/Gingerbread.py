# Copyright (c) 2022 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT

import nox


@nox.session
def lint(s):
    s.install("flake8")
    s.run("flake8", "gingerbread")


@nox.session
def format(s):
    s.install("isort", "black")
    s.run("isort", "gingerbread")
    s.run("black", "gingerbread", "noxfile.py")
