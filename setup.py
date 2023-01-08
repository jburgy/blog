from numpy.distutils.core import Extension

ext = Extension(
    name="fourt2py",
    sources=["fourt2py/fourt.pyf", "fourt2py/FOURT.F"],
    define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    extra_f77_compile_args=["-std=legacy", "-Wno-maybe-uninitialized"],
)

if __name__ == "__main__":
    from numpy.distutils.core import setup

    setup(name="fourt2py", ext_modules=[ext])
