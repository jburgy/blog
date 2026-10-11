# /// script
# requires-python = ">=3.13"
# ///

try:
    from concurrent import interpreters  # ty: ignore[unresolved-import]
except ImportError:
    import _interpreters as interpreters  # pyright: ignore[reportMissingImports]

from contextlib import closing

script = "import sys; print(sys.version_info)"
if run_string := getattr(interpreters, "run_string", None):
    interpreter = interpreters.create()
    run_string(interpreter, script)
    interpreters.destroy(interpreter)
else:
    with closing(interpreters.create()) as interpreter:  # ty: ignore[invalid-argument-type]
        interpreter.exec(script)
