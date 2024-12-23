from collections import defaultdict
from itertools import product

import networkx as nx

edges = defaultdict(set)
with open("aoc2024/day23input.txt", "rt") as lines:
    for line in lines:
        a, b = line.rstrip().split("-")
        edges[a].add(b)
        edges[b].add(a)

triples = set()
for node, nodes in edges.items():
    if str(node).startswith("t"):
        for a, b in product(nodes, nodes):
            if b in edges[a]:
                triples.add(tuple(sorted([a, b, node])))
print(len(triples))

g = nx.Graph()
with open("aoc2024/day23input.txt", "rt") as lines:
    g.add_edges_from(line.rstrip().split("-") for line in lines)

clique = nx.approximation.max_clique(g)
print(*sorted(clique), sep=",")
