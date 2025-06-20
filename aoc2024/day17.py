from collections.abc import Callable, Iterable


def compile(code: tuple[int, ...]) -> Callable[[int], Iterable[int]]:
    combo = "0123abc"
    instrs = (
        lambda op: f"a >>= {combo[op]}",
        lambda op: f"b ^= {op}",
        lambda op: f"b = {combo[op]} & 7",
        lambda _: "if not a: break",
        lambda _: "b ^= c",
        lambda op: f"yield {combo[op]} & 7",
        lambda op: f"b = a >> {combo[op]}",
        lambda op: f"c = a >> {combo[op]}",
    )

    lines = ["def func(a: int):", "    while True:"]
    for instr, op in zip(code[::2], code[1::2]):
        lines.append(f"        {instrs[instr](op)}")

    g: dict[str, Callable[[int], Iterable[int]]] = {}
    exec("\n".join(lines), g)
    return g["func"]


def findquine(code: tuple[int, ...]) -> None:
    combo = "0123abc"
    instrs = (
        lambda op: f"a >>= {combo[op]}",
        lambda op: f"b ^= {op}",
        lambda op: f"b = {combo[op]} & 7",
        lambda _: "",
        lambda _: "b ^= c",
        lambda op: f"constraints.append({combo[op]} & 7 == byte)",
        lambda op: f"b = a >> {combo[op]}",
        lambda op: f"c = a >> {combo[op]}",
    )

    lines = [
        "from z3 import BitVec, solve",
        "constraints = []",
        "a = BitVec('A', 51)",
        "for byte in prog:",
    ]
    for instr, op in zip(code[::2], code[1::2]):
        lines.append(f"    {instrs[instr](op)}")
    lines.append("constraints.append(a == 0)")
    lines.append("solve(*constraints)")

    exec("\n".join(lines), {"prog": prog})


prog = 2, 4, 1, 6, 7, 5, 4, 6, 1, 4, 5, 5, 0, 3, 3, 0
print(*compile(prog)(66171486), sep=",")
findquine(prog)
