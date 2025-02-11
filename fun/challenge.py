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
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    build_opener,
    urlopen
)
from zipfile import ZipFile

import numpy as np
from PIL import Image, ImageDraw


def asurl(s: str, ext: str = "html") -> str:
    return f"http://www.pythonchallenge.com/pc/def/{s}.{ext}"


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
    with urlopen(asurl(page)) as response:
        comments.feed(cast(HTTPResponse, response).read().decode())

    return "".join(c for c in cast(list[str], comments[-1]) if c.isalpha())


def equality(page: str) -> str:
    """expect: linked.html"""
    comments = CommentCollector()
    with urlopen(asurl(page)) as response:
        comments.feed(cast(HTTPResponse, response).read().decode())

    pattern = re.compile("(?<=[a-z][A-Z]{3})([a-z])(?=[A-Z]{3}[a-z])")
    return "".join(pattern.findall(comments[-1]))


def linkedlist(nothing: int) -> str:
    """expected: peak.html (at 66831)"""
    while True:
        with urlopen(asurl("linkedlist", f"php?{nothing=}")) as response:
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
    with urlopen(asurl(name, "p")) as response:
        lines = load(cast(HTTPResponse, response))
    return "\n".join(
        "".join(char * count for char, count in line)
        for line in lines
    )


def channel(name: str, nothing) -> str:
    """expect: hockey"""
    with urlopen(asurl(name, "zip")) as response:
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
    with urlopen(asurl(name, "png")) as response:
        image = Image.open(response)
    data = np.asarray(image)
    text = "".join(map(chr, data[48, :608:7, 0]))
    assert text.startswith("smart guy, you made it. the next level is ")
    return "".join(map(chr, ast.literal_eval(text[42:])))


def integrity() -> tuple[str, str]:
    un = bz2.decompress(
        b"BZh91AY&SYA\xaf\x82\r\x00\x00\x01\x01\x80\x02\xc0\x02"
        b"\x00 \x00!\x9ah3M\x07<]\xc9\x14\xe1BA\x06\xbe\x084"
    ).decode()
    pw = bz2.decompress(
        b"BZh91AY&SY\x94$|\x0e\x00\x00\x00\x81\x00\x03$ "
        b"\x00!\x9ah3M\x13<]\xc9\x14\xe1BBP\x91\xf08"
    ).decode()
    return un, pw


def good(name: str, un: str, pw: str) -> Image:
    mgr = HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, "http://www.pythonchallenge.com/pc/", un, pw)

    comments = CommentCollector()
    with build_opener(HTTPBasicAuthHandler(mgr)).open(
        f"http://www.pythonchallenge.com/pc/return/{name}.html"
    ) as response:
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
        x = ''.join(str(len(list(g))) + k for k, g in groupby(x))
    return len(x)


if __name__ == "__main__":
    # print(zero(2**38))
    # print(translate("map"))
    # print(ocr(ocr.__name__))
    # print(equality(equality.__name__))
    # print(linkedlist(12345))
    # print(banner(banner.__name__))
    # print(channel(channel.__name__, 90052))
    # print(oxygen(oxygen.__name__))
    # un, pw = integrity()
    # good(good.__name__, un=un, pw=pw).show()
    print(bull())
