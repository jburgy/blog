import _xxsubinterpreters as interpreters

interpreter_id = interpreters.create()
script = """from sys import version_info; print(version_info)"""

interpreters.run_string(interpreter_id, script)
