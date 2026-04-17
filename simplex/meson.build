simplex_source = custom_target('_simplexmodule.c',
    input : ['smplx.pyf'],
    output : ['_simplexmodule.c'],
    command: [py, '-m', 'numpy.f2py', '@INPUT@', '--build-dir', '@OUTDIR@'],
)

include_directories = run_command(py,
    ['-c', 'import numpy.f2py; print(numpy.get_include(), numpy.f2py.get_include())'],
    check : true
).stdout().split()

py.extension_module('simplex',
    'SMPLX.F',
    simplex_source,
    include_directories[1] / 'fortranobject.c',
    include_directories : include_directories,
    install : true,
    link_language : 'fortran',
)