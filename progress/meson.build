custom_target(
    input : 'binding.zig',
    output : 'binding.abi3.so',
    command: [py, '-m', 'pydust', 'build', '@OUTDIR@.@BASENAME@=@INPUT@'],
    install : true,
    install_dir : py.get_install_dir() / 'progress',
)

py.install_sources(['__init__.py', 'binding.pyi'], subdir : 'progress')
