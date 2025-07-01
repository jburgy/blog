custom_target('progress',
    input : ['build.zig', 'binding.zig'],
    output : ['binding.abi3.so'],
    command: [py, '-m', 'pydust', 'build', '--build-zig', '@INPUT0@', '--prefix', '@OUTDIR@', '@INPUT1@'],
    install : true,
    install_dir : py.get_install_dir() / 'progress',
)

py.install_sources(['__init__.py', 'binding.pyi'], subdir : 'progress')
