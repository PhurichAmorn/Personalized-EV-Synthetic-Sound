import sys

from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext


setup(
    name="ev-sound-lab-native-dsp",
    ext_modules=[Pybind11Extension(
        "audio._native_dsp",
        ["audio/" + name for name in (
            "bindings.cpp", "config.cpp", "dsp.cpp", "engine.cpp",
            "order.cpp", "random.cpp", "output.cpp",
        )],
        depends=["audio/" + name for name in ("engine.h", "dsp.h", "output.h")],
        libraries=["dl"] if sys.platform.startswith("linux") else [],
        cxx_std=17,
    )],
    cmdclass={"build_ext": build_ext},
)
