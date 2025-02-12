import ast
import bz2
import io
import re
from html.parser import HTMLParser
from http.client import HTTPResponse
from itertools import groupby
from pickle import load
from string import ascii_lowercase
from typing import cast
from urllib import request
from xmlrpc import client
from zipfile import ZipFile

import numpy as np
from PIL import Image, ImageDraw


def asurl(name: str, ext: str = "html", parent: str = "def") -> str:
    return f"http://www.pythonchallenge.com/pc/{parent}/{name}.{ext}"


def zero(n: int) -> str:
    """expect: 274877906944, redirects to map"""
    return str(n)


def translate(s: str) -> str:
    """expect: ocr"""
    table = str.maketrans(ascii_lowercase, ascii_lowercase[2:] + ascii_lowercase[:2])
    return s.translate(table)


class CommentCollector(HTMLParser, list):
    def handle_comment(self, data):
        self.append(data)


def ocr(page: str) -> str:
    """expect: equality"""
    comments = CommentCollector()
    with request.urlopen(asurl(page)) as response:
        comments.feed(cast(HTTPResponse, response).read().decode())

    return "".join(c for c in cast(list[str], comments[-1]) if c.isalpha())


def equality(page: str) -> str:
    """expect: linked.html"""
    comments = CommentCollector()
    with request.urlopen(asurl(page)) as response:
        comments.feed(cast(HTTPResponse, response).read().decode())

    pattern = re.compile("(?<=[a-z][A-Z]{3})([a-z])(?=[A-Z]{3}[a-z])")
    return "".join(pattern.findall(comments[-1]))


def linkedlist(nothing: int) -> str:
    """expected: peak.html (at 66831)"""
    while True:
        with request.urlopen(asurl("linkedlist", f"php?{nothing=}")) as response:
            parts = cast(HTTPResponse, response).read().decode().rpartition(" ")
            if parts[1] == " " and parts[0].endswith("and the next nothing is"):
                nothing = int(parts[2])
            elif parts[0] == "Yes. Divide by two and keep" and parts[2] == "going.":
                nothing //= 2
            else:
                return parts[2]


def peak() -> str:
    '''Hint: "pronounce it"'''
    return "pickle"


def banner(name: str) -> str:
    """expect: banner reading 'Channel'"""
    with request.urlopen(asurl(name, "p")) as response:
        lines = load(cast(HTTPResponse, response))
    return "\n".join("".join(char * count for char, count in line) for line in lines)


def channel(name: str, nothing) -> str:
    """expect: hockey"""
    with request.urlopen(asurl(name, "zip")) as response:
        bytes = cast(HTTPResponse, response).read()

    comments = []
    with ZipFile(io.BytesIO(bytes)) as myzip:
        while True:
            name = f"{nothing}.txt"
            comments.append(myzip.getinfo(name).comment.decode())
            with myzip.open(name) as file:
                parts = file.read().decode().rpartition(" ")
                if parts[1] == " " and parts[0] == "Next nothing is":
                    nothing = int(parts[2])
                else:
                    break
    return "".join(comments)


def hockey() -> str:
    """expect: oxygen"""
    return "oxygen"


def oxygen(name: str) -> str:
    """expect: integrity"""
    with request.urlopen(asurl(name, "png")) as response:
        image = Image.open(response)
    data = np.asarray(image)
    text = "".join(map(chr, data[48, :608:7, 0]))
    assert text.startswith("smart guy, you made it. the next level is ")
    return "".join(map(chr, ast.literal_eval(text[42:])))


def integrity() -> request.OpenerDirector:
    un = bz2.decompress(
        b"BZh91AY&SYA\xaf\x82\r\x00\x00\x01\x01\x80\x02\xc0\x02"
        b"\x00 \x00!\x9ah3M\x07<]\xc9\x14\xe1BA\x06\xbe\x084"
    ).decode()
    pw = bz2.decompress(
        b"BZh91AY&SY\x94$|\x0e\x00\x00\x00\x81\x00\x03$ "
        b"\x00!\x9ah3M\x13<]\xc9\x14\xe1BBP\x91\xf08"
    ).decode()
    mgr = request.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, "http://www.pythonchallenge.com/pc/", un, pw)
    return request.build_opener(request.HTTPBasicAuthHandler(mgr))


def good(name: str, opener: request.OpenerDirector) -> Image.Image:
    comments = CommentCollector()
    with opener.open(asurl("name", parent="return")) as response:
        comments.feed(cast(HTTPResponse, response).read().decode())
    lines = cast(list[str], comments)[-1].splitlines()
    first = tuple(map(int, "".join(lines[4:22]).split(",")))
    second = tuple(map(int, "".join(lines[24:29]).split(",")))

    image = Image.new("RGB", (500, 500))
    draw = ImageDraw.Draw(image)
    draw.polygon(first, fill="white")
    draw.polygon(second, fill="white")
    return image


def bull() -> int:
    """expect: 5808, see https://oeis.org/A005150"""
    x = "1"
    for _ in range(30):
        x = "".join(str(len(list(g))) + k for k, g in groupby(x))
    return len(x)


def cave(name: str, opener: request.OpenerDirector) -> Image.Image:
    with opener.open(asurl(name, ext="jpg", parent="return")) as response:
        image = Image.open(response)
    return Image.fromarray(np.asarray(image)[::2, ::2, :])


def evil2(name: str, opener: request.OpenerDirector) -> list[Image.Image]:
    with opener.open(asurl(name, ext="gfx", parent="return")) as response:
        data = cast(HTTPResponse, response).read()

    return [Image.open(io.BytesIO(data[start::5])) for start in range(5)]


def disproportional() -> str:
    transport = type("Transport", (client.Transport,), {"accept_gzip_encoding": False})
    with client.ServerProxy(
        "http://www.pythonchallenge.com/pc/phonebook.php", transport=transport()
    ) as proxy:
        return proxy.phone("Bert")


def italy(name: str, opener: request.OpenerDirector) -> Image.Image:
    with opener.open(asurl(name, ext="png", parent="return")) as response:
        image = Image.open(response)

    x = np.asarray(image)
    y = np.empty(shape=(100, 100, 3), dtype=x.dtype)

    top, bottom = 0, 100
    left, right = 0, 100
    direction = 0
    index = 0
    while top <= bottom and left <= right:
        if direction == 0:
            count = right - left
            y[top, left:right, :] = x[0, index: index + count, :]
            top += 1
        elif direction == 1:
            count = bottom - top
            y[top:bottom, right - 1, :] = x[0, index: index + count, :]
            right -= 1
        elif direction == 2:
            count = right - left
            y[bottom - 1, left:right, :] = x[0, index + count - 1: index - 1: -1, :]
            bottom -= 1
        elif direction == 3:
            count = bottom - top
            y[bottom - 1: top - 1: -1, left, :] = x[0, index: index + count, :]
            left += 1
        direction = (direction + 1) % 4
        index += count
    return Image.fromarray(y)


if __name__ == "__main__":
    # print(zero(2**38))
    # print(translate("map"))
    # print(ocr(ocr.__name__))
    # print(equality(equality.__name__))
    # print(linkedlist(12345))
    # print(banner(banner.__name__))
    # print(channel(channel.__name__, 90052))
    # print(oxygen(oxygen.__name__))
    opener = integrity()
    # good(good.__name__, opener=opener).show()
    # print(bull())
    # cave(cave.__name__, opener=opener).show()
    # for image in evil2(evil2.__name__, opener=opener):
    #     image.show()
    # print(disproportional())
    italy("wire", opener=opener).show()
