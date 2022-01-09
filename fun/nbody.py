# The Computer Language Benchmarks Game
# http://benchmarksgame.alioth.debian.org/
#
# originally by Kevin Carson
# modified by Tupteq, Fredrik Johansson, and Daniel Nanz
# modified by Maciej Fijalkowski

from numpy import add, array, divide, einsum, empty, fill_diagonal
from numpy import multiply, pi, power, subtract, sum

x = array([
    [0.0, 0.0, 0.0],
    [4.84143144246472090e+00, -1.16032004402742839e+00, -1.03622044471123109e-01],
    [8.34336671824457987e+00, 4.12479856412430479e+00, -4.03523417114321381e-01],
    [1.28943695621391310e+01, -1.51111514016986312e+01, -2.23307578892655734e-01],
    [1.53796971148509165e+01, -2.59193146099879641e+01, 1.79258772950371181e-01],
])
v = array([
    [0.0, 0.0, 0.0],
    [1.66007664274403694e-03, 7.69901118419740425e-03, -6.90460016972063023e-05],
    [-2.76742510726862411e-03, 4.99852801234917238e-03, 2.30417297573763929e-05],
    [2.96460137564761618e-03, 2.37847173959480950e-03, -2.96589568540237556e-05],
    [2.68067772490389322e-03, 1.62824170038242295e-03, -9.51592254519715870e-05],
]) * .36524
m = array([
    [1.0],
    [9.54791938424326609e-04],
    [2.85885980666130812e-04],
    [4.36624404335156298e-05],
    [5.15138902046611451e-05],
]) * 4 * pi**2

mm = m * m.T
divide(mm, m, out=mm)

v[0, :] = -sum(m * v, axis=0) / m[0, :]
d = empty(x.shape[:1] + x.shape)
r = empty(d.shape[:2])
a = empty(x.shape)

xi = x[:, None, :]
xj = x[None, :, :]
ri = r[:, :, None]

dt = .01

for _ in range(20_000):
    subtract(xi, xj, out=d)
    einsum("ijk,ijk->ij", d, d, out=r)  # d2 = sum(d * d, axis=2)
    fill_diagonal(r, 1.0)  # Avoid divide by zero warning
    power(r, -1.5, out=r)  # r = 1 / np.sqrt(d2)**3
    multiply(mm, r, out=r)  # r = mm / np.sqrt(d2)**3
    multiply(d, ri, out=d)
    sum(d, axis=1, out=a)
    multiply(a, dt, out=a)
    add(v, a, out=v)
    multiply(v, dt, out=a)
    add(x, a, out=x)

print(x)
