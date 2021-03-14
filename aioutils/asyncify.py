from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from functools import partial, wraps
from inspect import signature


def asyncify(f):
    loop = get_event_loop()

    @wraps(f)
    def wrapper(*args, **kwds):
        return loop.run_in_executor(None, partial(f, *args, **kwds))
    wrapper.__signature__ = signature(f)
    return wrapper


@asyncify
def readall(filename):
    with open(filename) as lines:
        return "".join(line for line in lines)


if __name__ == '__main__':
    help(readall)
    print(signature(readall))
    with closing(get_event_loop()) as loop, ThreadPoolExecutor() as executor:
        loop.set_default_executor(executor)
        content = loop.run_until_complete(readall("requirements.txt"))
        print(content)
