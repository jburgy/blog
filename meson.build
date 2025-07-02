project('blog', 'c',
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
    output : '_progress.abi3.so',
    command: [py, '-m', 'pydust', 'build', '_progress=@INPUT@'],
    install : true,
    install_dir : py.get_install_dir(),
)

subdir('fourt2py')
subdir('fun')
subdir('linear_programming')
subdir('progress')
subdir('sudoku')
