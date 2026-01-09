# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "jinja2",
#     "matplotlib==3.10.3",
#     "numpy==2.3.1",
#     "pandas==2.3.0",
# ]
# ///

import marimo  # pyright: ignore[reportMissingImports]  # ty: ignore[unresolved-import]

__generated_with = "0.14.8"
app = marimo.App()


@app.cell
def _():
    from colorsys import rgb_to_hls
    from matplotlib import colormaps, colors  # pyright: ignore[reportAttributeAccessIssue, reportMissingModuleSource]
    import numpy as np
    import pandas as pd

    if "RdWhGn" not in colormaps:
        colormaps.register(
            cmap=colors.LinearSegmentedColormap.from_list(
                "RdWhGn",
                ["#d65f5f", "#ffffff", "#5fba7d"],
            ),
            name="RdWhGn",
        )


    def centered_background_gradient(
        v,
        cmap="PuBu",
        low=0,
        high=0,
        text_color_threshold=0.408,
        vmin=None,
        vmax=None,
    ):
        colors = colormaps[cmap]([0, 0.5, 1])
        nh, nl, ns = rgb_to_hls(*colors[0, :3])
        ph, pl, ps = rgb_to_hls(*colors[2, :3])
        smin = v.min() if vmin is None else vmin
        smax = v.max() if vmax is None else vmax
        bg = pd.DataFrame(dict(
            h=np.where(v < 0, nh, ph) * 360,
            s=np.where(v < 0, ns, ps),
            l=np.where(v < 0, (nl - 1) * v / smin + 1, (pl - 1) * v / smax + 1),
        ), index=v.index)
        return [
            f"background-color: hsl({r.h:.2f}, {r.s:.2%}, {r.l:.2%});"
            for r in bg.itertuples()
        ]
    return centered_background_gradient, np, pd


@app.cell
def _(centered_background_gradient, np, pd):
    pd.DataFrame(np.transpose([
        [0.330, 4.87, 5.97, 0.073, 0.642, 1898, 568, 86.8, 102, 0.0146],
        [4879, 12104, 12756, 3475, 6792, 142984, 120536, 51118, 49528, 2370],
        [5427, 5243, 5514, 3340, 3933, 1326, 687, 1271, 1638, 2095],
        [3.7, 8.9, 9.8, 1.6, 3.7, 23.1, 9.0, 8.7, 11.0, 0.7],
        [4222.6, 2802.0, 24.0, 708.7, 24.7, 9.9, 10.7, 17.2, 16.1, 153.3],
        [57.9, 108.2, 149.6, 0.384, 227.9, 778.6, 1433.5, 2872.5, 4495.1, 5906.4],
        [167, 464, 15, -20, -65, -110, -140, -195, -200, -225],
        [0, 0, 1, 0, 2, 79, 82, 27, 14, 5],
    ]), index=pd.MultiIndex.from_tuples([
        ("Terrestial", "Mercury"),
        ("Terrestial", "Venus"),
        ("Terrestial", "Earth"),
        ("Terrestial", "Moon"),
        ("Terrestial", "Mars"),
        ("Jovian", "Jupiter"),
        ("Jovian", "Saturn"),
        ("Jovian", "Uranus"),
        ("Jovian", "Neptune"),
        ("Dwarf", "Pluto"),
    ], names=["Type", "Name"]), columns=[
        "Mass (10<sup>24</sup>kg)",
        "Diameter (km)",
        "Density (kg/m<sup>3</sup>)",
        "Gravity (m/s<sup>2</sup>)",
        "Length of day (hours)",
        "Distance from Sun (10<sup>6</sup>km)",
        "Mean temperature (°C)",
        "Number of moons",
    ]).style.format("{:0,.0f}").apply(centered_background_gradient, cmap="RdWhGn")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
