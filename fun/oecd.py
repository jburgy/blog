from json import load
from urllib.request import urlopen

import numpy as np
import pandas as pd


def _index_from(dimensions):
    return pd.MultiIndex.from_product([
        [value["name"] for value in dimension["values"]]
        for dimension in dimensions
    ], names=[dimension["name"] for dimension in dimensions])


def _generate(shape: tuple, mapping: dict, key, missing_value):
    missing = {key: missing_value}
    return (
        mapping.get(":".join(map(str, index)), missing)[key]
        for index in np.ndindex(shape)
    )


def oecd(dataset: str) -> pd.DataFrame:
    """ OECD dataset as pandas DataFrame

    heavily streamlined version of
    https://pandas-datareader.readthedocs.io/en/latest/remote_data.html#oecd
    See https://data.oecd.org/api/sdmx-ml-documentation/

    >>> pd.options.display.max_columns = 3
    >>> oecd("TUD")  #doctest: +NORMALIZE_WHITESPACE
    Year                                                1987  ...    1988
    Country Source              Series                        ...
    Hungary Administrative data Employees             4500.0  ...     NaN
                                Union members         4400.0  ...     NaN
                                Trade union  density    97.8  ...     NaN
            Survey data         Employees                NaN  ...     NaN
                                Union members            NaN  ...     NaN
    ...                                                  ...  ...     ...
    Germany Administrative data Union members         7868.0  ...  7888.0
                                Trade union  density    33.3  ...    33.1
            Survey data         Employees                NaN  ...     NaN
                                Union members            NaN  ...     NaN
                                Trade union  density     NaN  ...     NaN
    <BLANKLINE>
    [216 rows x 59 columns]
    >>>
    """
    with urlopen(
        f"http://stats.oecd.org/SDMX-JSON/data/{dataset}/all/all?"
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
