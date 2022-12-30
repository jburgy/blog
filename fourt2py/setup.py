from numpy.distutils.core import Extension

ext = Extension(
    name="fourt",
    sources=["fourt.pyf", "FOURT.F"],
    define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    f2py_options=["-std=legacy"],
)

if __name__ == "__main__":
    from numpy.distutils.core import setup

    setup(name="fourt", ext_modules=[ext])
