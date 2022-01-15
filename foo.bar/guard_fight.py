""""
Uh-oh - you've been cornered by one of Commander Lambdas elite guards!
Fortunately, you grabbed a beam weapon from an abandoned guard post while you
were running through

the station, so you have a chance to fight your way out. But the beam weapon
is potentially dangerous to you as well as to the elite guard: its beams
reflect off walls, meaning you'll have to be very careful where you shoot to
avoid bouncing a shot toward yourself!
Luckily, the beams can only travel a certain maximum distance before becoming
too weak to cause damage. You also know that if a beam hits a corner, it will
bounce back in exactly the same direction. And of course, if the beam hits
either you or the guard, it will stop immediately (albeit painfully).

Write a function solution(dimensions, your_position, guard_position, distance)
that gives an array of 2 integers of the width and height of the room, an
array of 2 integers of your x and y coordinates in the room, an array of 2
integers of the guard's x and y coordinates in the room, and returns an integer
of the number of distinct directions that you can fire to hit the elite guard,
given the maximum distance that the beam can travel.

The room has integer dimensions [1 < x_dim <= 1250, 1 < y_dim <= 1250]. You and
the elite guard are both positioned on the integer lattice at different
distinct positions (x, y) inside the room such that [0 < x < x_dim,
0 < y < y_dim]. Finally, the maximum distance that the beam can travel before
becoming harmless will be given as an integer 1 < distance <= 10000.

For example, if you and the elite guard were positioned in a room with
dimensions [3, 2], your_position [1, 1], guard_position [2, 1], and a maximum
shot distance of 4, you could shoot in seven different directions to hit the
elite guard (given as vector bearings from your location): [1, 0], [1, 2],
[1, -2], [3, 2], [3, -2], [-3, 2], and [-3, -2]. As specific examples, the shot
at bearing [1, 0] is the straight line horizontal shot of distance 1, the shot
at bearing [-3, -2] bounces off the left wall and then the bottom wall before
hitting the elite guard with a total shot distance of sqrt(13), and the shot at
bearing [1, 2] bounces off just the top wall before hitting the elite guard
with a total shot distance of sqrt(5).


Test cases
==========
Your code should pass the following test cases.
Note that it may also be run against hidden test cases not shown here.

-- Python cases --
Input:
solution.solution([3,2], [1,1], [2,1], 4)
Output:
  7

Input:
solution.solution([300,275], [150,150], [185,100], 500)
Output:
  9
"""

from collections import defaultdict
from math import gcd


def solution(dimensions, your_position, trainer_position, distance):
    w, h = dimensions
    yx, yy = your_position
    tx, ty = trainer_position
    y = [
        [complex(0, 0), complex(0, h - 2 * yy)],
        [complex(w - 2 * yx, 0), complex(w - 2 * yx, h - 2 * yy)],
    ]
    t = [
        [complex(tx - yx, ty - yy), complex(tx - yx, h - ty - yy)],
        [complex(w - tx - yx, ty - yy), complex(w - tx - yx, h - ty - yy)],
    ]
    m = distance // w + 3
    n = distance // h + 3

    def normalize(z):
        real = int(z.real)
        imag = int(z.imag)
        g = gcd(real, imag)
        return complex(real // g, imag // g) if g else z

    dp1 = distance + 1
    ts = defaultdict(lambda: dp1)
    ys = defaultdict(lambda: dp1)
    for i in range(-m, m):
        yi = y[i & 1]
        ti = t[i & 1]
        for j in range(-n, n):
            bounce = complex(w * i, h * j)

            tij = ti[j & 1] + bounce
            td = abs(tij)
            tp = normalize(tij)
            if td < ts[tp]:
                ts[tp] = td

            if not bounce:
                continue

            yij = yi[j & 1] + bounce
            if not yij:
                ys[normalize(bounce)] = 0
                continue

            yd = abs(yij)
            yp = normalize(yij)
            if yd < ys[yp]:
                ys[yp] = yd

    return sum(v <= distance and v < ys[k] for k, v in ts.items())


assert solution([3, 2], [1, 1], [2, 1], 4) == 7
assert solution([300, 275], [150, 150], [185, 100], 500) == 9
assert solution([300, 275], [150, 150], [185, 100], 30) == 0
assert solution([1250, 2], [0, 0], [1249, 1], 10_000) == 127324
assert solution([1250, 1250], [625, 625], [0, 0], 10_000) == 41
assert solution([2, 1], [0, 0], [1, 0], 1) == 1
assert solution([2, 5], [1, 2], [1, 4], 11) == 27
assert solution([10, 10], [4, 4], [3, 3], 5000) == 739323
assert solution([23, 10], [6, 4], [3, 2], 23) == 8
assert solution([42, 59], [34, 44], [6, 34], 5000) == 30904
