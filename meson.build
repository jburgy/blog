project('blog',
    version : '0.1',
    default_options : [
        'optimization=3',
        'warning_level=1',
        'fortran_std=legacy',
    ]
)

# languages in project() are detected for host *and* build machine; we only need host
add_languages('c', 'fortran', native : false)

add_project_arguments(
    '-pthread',
    '-Wno-unused-parameter',
    '-Wsign-compare',
    '-DNDEBUG',
    '-fwrapv',
    '-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION',
    '-DNPY_DISABLE_OPTIMIZATION=1',
    '-fPIC',
    '-finput-charset=UTF-8',
    language : 'c')

add_project_arguments(
    '-ffixed-form',
    '-fno-second-underscore',
    '-fPIC',
    '-Wno-maybe-uninitialized',
    language : 'fortran')

py = import('python').find_installation()

# meson rejects absolute paths into the source tree (e.g. numpy in an in-tree .venv)
f2py_incdirs = run_command(py,
    ['-c', 'import os, sys, numpy, numpy.f2py; print(*(os.path.relpath(p, sys.argv[1]) for p in (numpy.get_include(), numpy.f2py.get_include())))',
     meson.current_source_dir()],
    check : true
).stdout().split()
f2py_inc = include_directories(f2py_incdirs)
fortranobject_c = files(f2py_incdirs[1] / 'fortranobject.c')
# output must be '<python module name>module.c' as declared inside the .pyf
f2py_command = [py, '-m', 'numpy.f2py', '@INPUT@', '--build-dir', '@OUTDIR@']

subdir('fourt2py')
subdir('fun')
subdir('linprog')
if get_option('progress')
    subdir('progress')
endif
subdir('simplex')
subdir('sudoku')
