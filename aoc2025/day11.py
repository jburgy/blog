from graphlib import TopologicalSorter


def count_paths(
    graph: dict[str, list[str]], *targets: str
) -> dict[str, dict[str, int]]:
    counts = {target: {target: 1} for target in targets}
    for current in TopologicalSorter(graph).static_order():
        for count in counts.values():
            count[current] = sum(
                map(count.__getitem__, graph.get(current, [])),
                count.get(current, 0),
            )
    return counts


graph = {}
with open("aoc2025/day11input.txt", "rt") as lines:
    for line in lines:
        source, _, targets = line.rstrip().partition(":")
        graph[source] = targets.split()

counts = count_paths(graph, "out", "dac", "fft")

print(counts["out"]["you"])
print(
    counts["dac"]["svr"] * counts["fft"]["dac"] * counts["out"]["fft"]
    + counts["fft"]["svr"] * counts["dac"]["fft"] * counts["out"]["dac"]
)
