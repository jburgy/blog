project('fourt2py', 'c',
    version : '0.1',
    default_options : [
        'optimization=3',
        'warning_level=1',
        'fortran_std=legacy',
    ]
)

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

py_mod = import('python')
py3 = py_mod.find_installation('python3')
py3_dep = py3.dependency()
message(py3.path())
message(py3.get_install_dir())

incdir_numpy = run_command(py3,
    ['-c', 'import os; os.chdir(".."); import numpy; print(numpy.get_include())'],
    check : true
).stdout().strip()

incdir_f2py = run_command(py3,
    ['-c', 'import os; os.chdir(".."); import numpy.f2py; print(numpy.f2py.get_include())'],
    check : true
).stdout().strip()

fourt2py_source = custom_target('fourt2pymodule.c',
    input : ['fourt.pyf'],
    output : ['fourt2pymodule.c'],
    command: [py3, '-m', 'numpy.f2py', '@INPUT@'],
)

inc_np = include_directories(incdir_numpy, incdir_f2py)

py3.extension_module('fourt2py',
    'FOURT.F',
    fourt2py_source,
    incdir_f2py + '/fortranobject.c',
    include_directories : inc_np,
    dependencies : py3_dep,
    install : true,
)