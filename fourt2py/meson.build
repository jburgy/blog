fourt2py_source = custom_target(
    input : 'fourt.pyf',
    output : 'fourt2pymodule.c',
    command : f2py_command,
)

py.extension_module('fourt2py',
    'FOURT.F',
    fourt2py_source,
    fortranobject_c,
    include_directories : f2py_inc,
    install : true,
    link_language : 'fortran',
)