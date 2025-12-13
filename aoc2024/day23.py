# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "networkx",
# ]
# ///

import networkx as nx # pyright: ignore[reportMissingModuleSource]

g: nx.Graph = nx.Graph()
with open("aoc2024/day23input.txt", "rt") as lines:
    g.add_edges_from(line.rstrip().split("-") for line in lines)  # pyright: ignore[reportArgumentType]

cycles = sum(
    any(str(node).startswith("t") for node in cycle)
    for cycle in nx.simple_cycles(g, length_bound=3)
)
print(cycles)

clique = nx.approximation.max_clique(g)
print(*sorted(clique), sep=",")

