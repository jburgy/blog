try:
    import _xxsubinterpreters as interpreters  # type: ignore[import-not-found]
except ModuleNotFoundError:
    from interpreters_backport import interpreters  # type: ignore[import-untyped]

from contextlib import closing

script = "import sys; print(sys.version_info)"
if run_string := getattr(interpreters, "run_string", None):
    interpreter = interpreters.create()
    run_string(interpreter, script)
    interpreters.destroy(interpreter)
else:
    with closing(interpreters.create()) as interpreter:
        interpreter.exec(script)
