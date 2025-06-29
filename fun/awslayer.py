"""Package your layer content for AWS Lambda.

To create a layer, bundle your packages into a .zip file archive that meets the
following requirements:

* Build the layer using the same Python version that you plan to use for the Lambda
function. For example, if you build your layer using Python 3.13, use the Python 3.13
runtime for your function.
* Your .zip file must include a python directory at the root level.
* The packages in your layer must be compatible with Linux. Lambda functions run on
Amazon Linux.
* If your layer includes native binaries or executable files, they must target the same
architecture (x86_64 or arm64) as your function.

You can create layers that contain either third-party Python libraries installed with
pip (such as requests or pandas) or your own Python modules and packages.

See https://docs.aws.amazon.com/lambda/latest/dg/python-layers.html#python-layers-package
"""

import sysconfig
from argparse import ArgumentParser
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from shutil import get_terminal_size
from signal import SIGWINCH, SIG_DFL, signal
from types import FrameType
from typing import Any, Callable
from zipfile import ZipFile

platlib = Path(sysconfig.get_path("platlib"))


@contextmanager
def tail(max_lines: int) -> Generator[Callable[[str], None], None, None]:
    lines = deque(maxlen=max_lines)
    escape = "\N{ESC}"
    clrscr = f"{escape}[{max_lines}F{escape}[J"
    columns = -1

    def onwinch(signum: int, frame: FrameType | None) -> Any:
        nonlocal columns
        columns, _lines = get_terminal_size()

    def inner(line: str) -> None:
        full = len(lines) >= max_lines
        line = line[:columns]
        lines.append(line)
        if full:
            print(clrscr, end="")
            print(*lines, sep="\n")
        else:
            print(line)

    signal(SIGWINCH, onwinch)
    onwinch(SIGWINCH, None)

    try:
        yield inner
    finally:
        signal(SIGWINCH, SIG_DFL)
        print(clrscr, end="")


def main():
    parser = ArgumentParser()
    parser.add_argument("zipfile", nargs="?", default="layer.zip")
    args = parser.parse_args()

    with tail(max_lines=5) as taylor, ZipFile(args.zipfile, "w") as zf:
        for root, dirs, files in platlib.walk():
            taylor(str(root))
            for file in files:
                path = root / file
                zf.write(
                    filename=path, arcname=Path("python") / path.relative_to(platlib)
                )


if __name__ == "__main__":
    main()
