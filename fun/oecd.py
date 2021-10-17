from json import load
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd


def _index_from(dimensions):
    return pd.MultiIndex.from_product(
        [[value["name"] for value in dimension["values"]] for dimension in dimensions],
        names=[dimension["name"] for dimension in dimensions],
    )


def _generate(shape: tuple, mapping: dict, key, missing_value):
    missing = {key: missing_value}
    return (
        mapping.get(":".join(map(str, index)), missing)[key]
        for index in np.ndindex(shape)
    )


def oecd(dataset: str, **kwargs) -> pd.DataFrame:
    """OECD dataset as pandas DataFrame

    heavily streamlined version of
    https://pandas-datareader.readthedocs.io/en/latest/remote_data.html#oecd
    See https://data.oecd.org/api/sdmx-ml-documentation/

    >>> pd.options.display.max_columns = 5
    >>> (
    ...     oecd("TUD", startTime=1960, endTime=2020)
    ...     .reorder_levels(["Frequency", "Measure", "Country"])
    ...     .loc["Annual", "Percentage of employees"].head()
    ... ) #doctest: +NORMALIZE_WHITESPACE
    Time                  1960       1961  ...       2019       2020
    Country                                ...
    Australia        53.799999  53.200001  ...        NaN        NaN
    Austria          60.099998  59.599998  ...  26.299999        NaN
    Belgium          41.500000  40.400002  ...  49.099998        NaN
    Canada           30.100000  29.500000  ...  26.100000  27.200001
    Czech Republic         NaN        NaN  ...        NaN        NaN
    <BLANKLINE>
    [5 rows x 61 columns]
    >>>
    """
    with urlopen(
        f"http://stats.oecd.org/SDMX-JSON/data/{dataset}/all/all?" + urlencode(kwargs)
    ) as response:
        sdmx = load(response)

    index = _index_from(sdmx["structure"]["dimensions"]["series"])
    columns = _index_from(sdmx["structure"]["dimensions"]["observation"])

    data = (
        list(_generate(columns.levshape, row, 0, np.nan))
        for row in _generate(
            index.levshape, sdmx["dataSets"][0]["series"], "observations", {}
        )
    )
    return pd.DataFrame(data, index=index, columns=columns)
