# Anti-REA Python 构建集成（FR-D5）
# 在 setuptools 的 build_ext 之后调用集成驱动施加保护（不内嵌引擎）。
#
# 用法（setup.py）：
#   from anti_rea_build_ext import AntiReaBuildExt
#   setup(..., cmdclass={"build_ext": AntiReaBuildExt})
import os
import subprocess
import sys

from setuptools.command.build_ext import build_ext


class AntiReaBuildExt(build_ext):
    """扩展构建完成后，对源码施加保护并验证（FR-D5 / FR-D7）。"""

    def run(self):
        super().run()
        root = os.path.abspath(os.path.dirname(self.distribution.script_name)
                               or os.getcwd())
        driver = os.environ.get(
            "ANTI_REA_DRIVER",
            os.path.join(root, "..", "..", "anti-rea"))
        out = os.path.join(root, os.environ.get("ANTI_REA_OUT", "anti-rea"))
        cmd = [driver, "pipeline", "--root", root, "--out", out,
               "--abort-on-failure"]
        for src in os.environ.get("ANTI_REA_SOURCES", "").split(os.pathsep):
            if src:
                cmd += ["--source", src]
        rc = subprocess.call(cmd)
        if rc != 0:
            sys.exit("Anti-REA 保护/验证失败，构建中止（FR-D7）")
