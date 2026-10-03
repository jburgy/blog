# combination.py runs standalone (`uv run --script`) where `from forth import
# ForthCompiler` resolves to the sibling forth.py, not this package. Re-export
# it here so the same import also works when pytest collects combination.py
# as the forth.combination submodule.
from .forth import ForthCompiler  # noqa: F401
