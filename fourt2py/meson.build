add_languages('fortran')
add_project_arguments(
    '-pthread',
    '-Wno-unused-parameter',
    '-Wsign-compare',
    '-DNDEBUG',
    '-fwrapv',
    '-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION',
    '-DNPY_DISABLE_OPTIMIZATION=1',
    '-fPIC',
    language : 'c')
add_project_arguments(
    '-ffixed-form',
    '-fno-second-underscore',
    '-fPIC',
    '-Wno-maybe-uninitialized',
    language : 'fortran')

fourt2py_source = custom_target('fourt2pymodule.c',
    input : ['fourt.pyf'],
    output : ['fourt2pymodule.c'],
    command: [py, '-m', 'numpy.f2py', '@INPUT@', '--build-dir', '@OUTDIR@'],
)

incdir = run_command(py,
    ['-c', 'import numpy.f2py; print(numpy.f2py.get_include())'],
    check : true
).stdout().strip()

py.extension_module('fourt2py',
    'FOURT.F',
    fourt2py_source,
    incdir / 'fortranobject.c',
    include_directories : include_directories(incdir),
    dependencies : [py.dependency(), dependency('numpy')],
    install : true,
)