import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from setuptools import Extension, setup

from anti_rea_build_ext import AntiReaBuildExt

HERE = os.path.dirname(os.path.abspath(__file__))
APP_C = os.path.join(HERE, "src", "app.c")
os.environ.setdefault("ANTI_REA_SOURCES", APP_C)

setup(
    name="anti_rea_py_example",
    version="0.0.0",
    ext_modules=[Extension("app", [APP_C],
                           define_macros=[("ANTI_REA_EXT", "1")])],
    cmdclass={"build_ext": AntiReaBuildExt},
)
