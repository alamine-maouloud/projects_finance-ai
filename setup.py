"""Builds the optional native kernel (mcrisk._native). If no C++17 compiler
is available the package still installs and falls back to NumPy."""

from setuptools import setup

try:
    from pybind11.setup_helpers import Pybind11Extension, build_ext
except ImportError:  # pybind11 missing: pure-Python install
    setup()
else:
    class OptionalBuildExt(build_ext):
        def run(self):
            try:
                super().run()
            except Exception as exc:  # noqa: BLE001
                print(f"warning: native kernel not built ({exc}); using NumPy backend")

    setup(
        ext_modules=[Pybind11Extension(
            "mcrisk._native",
            ["cpp/src/credit_kernel.cpp", "cpp/src/bindings.cpp"],
            include_dirs=["cpp/src"],
            cxx_std=17,
            extra_compile_args=["-O3"],
        )],
        cmdclass={"build_ext": OptionalBuildExt},
    )
