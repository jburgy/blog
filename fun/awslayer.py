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
from pathlib import Path
from zipfile import ZipFile

from progress import Progress

platlib = Path(sysconfig.get_path("platlib"))


def main():
    parser = ArgumentParser()
    parser.add_argument("zipfile", nargs="?", default="layer.zip")
    args = parser.parse_args()

    node = Progress()
    parents: list[tuple[Path, Progress]] = []

    with ZipFile(args.zipfile, "w") as zf:
        for root, dirs, files in platlib.walk():
            for parent, node in reversed(parents):
                try:
                    extra = root.relative_to(parent)
                    node = node.start(str(extra), 0)
                    parents.append((root, node))
                    break
                except ValueError:
                    node.end()
                    parents.pop()
            else:
                node = node.start(root.name, 0)
                parents.append((root, node))
            for file in files:
                node.completeOne()
                path = root / file
                zf.write(
                    filename=path, arcname=Path("python") / path.relative_to(platlib)
                )

    for _, node in reversed(parents):
        node.end()


if __name__ == "__main__":
    main()
