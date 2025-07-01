custom_target('progress',
    input : 'build.zig',
    output : ['binding.abi3.so'],
    command: [py, '-m', 'ziglang', 'build', '--build-file', '@INPUT@', '--prefix', '@OUTDIR@'],
    install : true,
    install_dir : py.get_install_dir() / 'progress',
)

py.install_sources(['__init__.py', 'binding.pyi'], subdir : 'progress')
