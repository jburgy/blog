fs = import('fs')

fs.copyfile(py.get_path('platlib') / 'pydust' / 'src' / 'pydust.build.zig', 'pydust.build.zig' )

custom_target('progress',
    input : 'build.zig',
    output : ['progress.abi3.so'],
    command: [py, '-m', 'pydust', 'build', '--prefix', '@OUTDIR@/progress', '--build-file', '@INPUT@'],
    install : true,
    install_dir : py.get_install_dir(),
)

py.install_sources(['__init__.py', 'binding.pyi'], subdir : 'progress')
