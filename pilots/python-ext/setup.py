import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_integrations(start):
    """定位仓库内的 integrations/python（优先环境变量，其次向上查找）。"""
    env = os.environ.get("ANTI_REA_INTEGRATIONS")
    if env and os.path.isdir(env):
        return env
    d = start
    while True:
        cand = os.path.join(d, "integrations", "python")
        if os.path.isdir(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


_INT = _find_integrations(HERE)
if _INT is None:
    sys.exit("pilotext: 未找到 integrations/python（请在 Anti-REA 仓库内构建）")
sys.path.insert(0, _INT)

from setuptools import Extension, setup  # noqa: E402

from anti_rea_build_ext import AntiReaBuildExt  # noqa: E402

SRC = os.path.join(HERE, "src", "transform.c")
os.environ.setdefault("ANTI_REA_SOURCES", SRC)

setup(
    name="pilotext",
    version="0.0.0",
    ext_modules=[Extension("pilotext", [SRC],
                           define_macros=[("ANTI_REA_EXT", "1")])],
    cmdclass={"build_ext": AntiReaBuildExt},
)
