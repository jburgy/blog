simplex_source = custom_target(
    input : 'smplx.pyf',
    output : '_simplexmodule.c',
    command : f2py_command,
)

py.extension_module('_simplex',
    'SMPLX.F',
    simplex_source,
    fortranobject_c,
    include_directories : f2py_inc,
    install : true,
    link_language : 'fortran',
)