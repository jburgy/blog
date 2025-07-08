# pyright: reportAttributeAccessIssue=false, reportInvalidTypeForm=false, reportPrivateImportUsage=false

import marimo

__generated_with = "0.14.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import numpy as np
    from scipy.linalg import blas

    # fmt: off
    x = np.array([
        [0.0, 0.0, 0.0],
        [4.84143144246472090e+00, -1.16032004402742839e+00, -1.03622044471123109e-01],
        [8.34336671824457987e+00, 4.12479856412430479e+00, -4.03523417114321381e-01],
        [1.28943695621391310e+01, -1.51111514016986312e+01, -2.23307578892655734e-01],
        [1.53796971148509165e+01, -2.59193146099879641e+01, 1.79258772950371181e-01],
    ]).T
    v = np.array([
        [0.0, 0.0, 0.0],
        [1.66007664274403694e-03, 7.69901118419740425e-03, -6.90460016972063023e-05],
        [-2.76742510726862411e-03, 4.99852801234917238e-03, 2.30417297573763929e-05],
        [2.96460137564761618e-03, 2.37847173959480950e-03, -2.96589568540237556e-05],
        [2.68067772490389322e-03, 1.62824170038242295e-03, -9.51592254519715870e-05],
    ]).T * 365.24
    m = np.array([
        1.0,
        9.54791938424326609e-04,
        2.85885980666130812e-04,
        4.36624404335156298e-05,
        5.15138902046611451e-05,
    ]) * 4 * np.pi**2
    # fmt: on

    # v[:, 0] = -sum(m * v, axis=1) / m[0]
    a = np.empty(x.shape, dtype=complex)

    jm = m * -1j
    n = x.shape[1]
    # see https://stackoverflow.com/a/52564537/8479938
    # only need upper triangle plus diagonal hence ½ n x (n + 1)
    ap = np.empty((3, n * (n + 1) // 2), dtype=complex)
    xxT = np.empty(ap.shape[1], dtype=float)
    where = np.empty(ap.shape, dtype=bool)
    d = np.empty(ap.shape[1], dtype=float)
    trid = np.r_[0, 2 : n + 1].cumsum()
    x2 = np.empty(n, dtype=float)
    ones = np.empty(n, dtype=float)
    ones.fill(1.0)

    dt = 0.01
    xs = np.empty((20_000, *x.shape))

    for xt in xs:
        a.real = x
        a.imag.fill(-1.0)
        ap.fill(0.0)
        for i in range(3):  # A += α z z*
            blas.zhpr(n, alpha=-2.0, x=a[i], ap=ap[i], overwrite_ap=True)
        np.sum(ap.real, axis=0, out=xxT)
        xxT += 6
        np.take(xxT, trid, out=x2)
        # A += α (x yᵀ + y xᵀ)
        blas.dspr2(n, alpha=-0.5, x=x2, y=ones, ap=xxT, overwrite_ap=True)

        np.sqrt(xxT, out=d)
        np.multiply(xxT, d, out=xxT)
        np.greater(xxT, 0.0, out=where)
        np.divide(ap.imag, xxT, where=where, out=ap.imag)

        for i in range(3):  # y = α A x + β y
            blas.zhpmv(n, alpha=0.5, ap=ap[i], x=jm, beta=0.0, y=a[i], overwrite_y=True)

        blas.daxpy(a=dt, x=a.real, y=v)  # v += a dt
        blas.daxpy(a=dt, x=v, y=x)  # x += v dt

        xt[:] = x  # pyright: ignore[reportIndexIssue]
    return (xs,)


@app.cell
def _(m, np, xs):
    import marimo as mo
    import numpy.typing as npt
    from matplotlib import animation, pyplot as plt

    def update_lines(
        num: int, xs: npt.NDArray[np.float32], lines: list[plt.Line2D]
    ) -> list[plt.Line2D]:
        for i, line in enumerate(lines):
            line.set_data_3d(xs[i, :, : num * 100 : 100])
        return lines

    # Attaching 3D axis to the figure
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")

    # Create lines initially without data
    lines = [ax.plot([], [], [])[0] for _ in m]

    # Setting the Axes properties
    ax.set(xlim3d=(xs[:, 0, :].min(), xs[:, 0, :].max()), xlabel="X")
    ax.set(ylim3d=(xs[:, 1, :].min(), xs[:, 1, :].max()), ylabel="Y")
    ax.set(zlim3d=(xs[:, 2, :].min(), xs[:, 2, :].max()), zlabel="Z")

    # Creating the Animation object
    ani = animation.FuncAnimation(
        fig=fig,
        func=update_lines,
        frames=len(xs) // 100,
        fargs=(xs.T, lines),
        interval=30,
    )
    mo.mpl.interactive(ani._fig)
    return


if __name__ == "__main__":
    app.run()
