"""Numeric data cleaning utilities for Portuguese format numbers."""

import pandas as pd

def clean_numeric_column(series: pd.Series) -> pd.Series:
    if series.empty:
        return series

    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)

    # is_object_dtype não detecta StringDtype do Polars — checar ambos
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        cleaned = (
            series.astype(str)
            .str.strip()
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        return pd.to_numeric(cleaned, errors="coerce")

    return pd.to_numeric(series, errors="coerce")