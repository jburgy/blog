project('blog', 'c', 'fortran',
    version : '0.1',
    default_options : [
        'optimization=3',
        'warning_level=1',
        'fortran_std=legacy',
    ]
)

py = import('python').find_installation()

subdir('fourt2py')
subdir('fun')
subdir('linprog')
subdir('progress')
subdir('sudoku')
