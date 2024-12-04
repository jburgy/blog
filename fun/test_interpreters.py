try:
    import interpreters
except ModuleNotFoundError:
    from interpreters_backport import interpreters

from contextlib import closing

script = "import sys; print(sys.version_info)"

with closing(interpreters.create()) as interpreter:
    interpreter.exec(script)
