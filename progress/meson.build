custom_target(
    input : 'build.zig',
    output : 'binding.abi3.so',
    command: [
        py,
        '-m',
        'ziglang',
        'build',
        '-Dinclude=' + py.get_path('include'),
        '-Dstdlib=' + py.get_path('stdlib'),
        '--verbose',
        '--build-file',
        '@INPUT@',
    ],
    install : true,
    install_dir : py.get_install_dir() / 'progress',
)

py.install_sources(['__init__.py', 'binding.pyi'], subdir : 'progress')
