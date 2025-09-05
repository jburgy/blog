import re
import subprocess

import pytest
from playwright.async_api import Page, expect

@pytest.fixture(scope="module", autouse=True)
def emrun(target: str = "4th.html"):
    subprocess.run(["make", target], cwd="forth", check=True)
    proc = subprocess.Popen(
        ["emrun", "--no_browser", "--serve_after_exit", target],
        stdout=subprocess.PIPE,
        cwd="forth",
        text=True
    )
    for line in proc.stdout:
        if line.startswith("Now listening at"):
            break

    yield

    proc.terminate()
    proc.wait()



@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("65 EMIT", "A"),
        ("777 65 EMIT", "A"),
        ("32 DUP + 1+ EMIT", "A"),
        ("16 DUP 2DUP + + + 1+ EMIT", "A"),
        ("8 DUP * 1+ EMIT", "A"),
        ("CHAR A EMIT", "A"),
        (": SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT", "A"),
        (f"{int.from_bytes('65'.encode(), 'little'):d} DSP@ 2 NUMBER DROP EMIT", "A"),
        ("64 >R RSP@ 1 TELL RDROP", "@"),
        ("65 DSP@ RSP@ SWAP C@C! RSP@ 1 TELL", "A"),
        ("64 >R 1 RSP@ +! RSP@ 1 TELL", "A"),
        (
            """
: <BUILDS WORD CREATE DODOES , 0 , ;
: DOES> R> LATEST @ >DFA ! ;
: CONST <BUILDS , DOES> @ ;

65 CONST FOO
FOO EMIT
""",
            "A"
        ),
    ])
@pytest.mark.asyncio(loop_scope="session")
async def test_has_title(page: Page, test_input: str, expected: str):
    page.once("dialog", lambda dialog: dialog.accept(test_input))
    await page.goto("http://localhost:6931/4th.html")

    # Expect a title "to contain" a substring.
    await expect(page.locator("#output")).to_have_value(re.compile(expected))
