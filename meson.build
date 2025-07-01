project('fourt2py', 'c',
    version : '0.1',
    default_options : [
        'optimization=3',
        'warning_level=1',
        'fortran_std=legacy',
    ]
)

py = import('python').find_installation()

custom_target(
    input : 'progress/binding.zig',
    output : 'binding.abi3.so',
    command: [py, '-m', 'pydust', 'build', 'binding=@INPUT@'],
    install : true,
    install_dir : py.get_install_dir() / 'progress',
)

subdir('fourt2py')
subdir('fun')
subdir('linear_programming')
subdir('progress')
subdir('sudoku')
