project('blog', 'c', 'fortran',
    version : '0.1',
    default_options : [
        'optimization=3',
        'warning_level=1',
        'fortran_std=legacy',
    ]
)

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

subdir('fourt2py')
subdir('fun')
subdir('linprog')
subdir('progress')
subdir('simplex')
subdir('sudoku')
