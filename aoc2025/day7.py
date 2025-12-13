from pathlib import Path

lines = Path("aoc2025/day7input.txt").read_text().splitlines()

beams = {i: 1 for i, ch in enumerate(lines[0]) if ch == "S"}
splits = 0
for line in lines[1:]:
    new_beams = {}
    for i, timelines in beams.items():
        if line[i] == "^":
            splits += 1
            new_beams[i - 1] = new_beams.get(i - 1, 0) + timelines
            new_beams[i + 1] = new_beams.get(i + 1, 0) + timelines
        else:
            new_beams[i] = new_beams.get(i, 0) + timelines
    beams = new_beams
print(splits)
print(sum(beams.values()))
