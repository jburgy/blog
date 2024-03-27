import _xxsubinterpreters as interpreters

interpreter_id = interpreters.create()
script = "import sys; print(sys.version_info)"

interpreters.run_string(interpreter_id, script)
interpreters.destroy(interpreter_id)
