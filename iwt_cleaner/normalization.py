from __future__ import annotations
import re
import pandas as pd
from pandas.api.types import is_numeric_dtype

def detect_mode(df: pd.DataFrame) -> str:
    """Heuristic: tidy if single 'value' column (or mostly non-numeric columns); else table."""
    numeric_cols = [c for c in df.columns if is_numeric_dtype(df[c])]
    if "value" in df.columns or len(numeric_cols) <= max(1, int(len(df.columns) * 0.2)):
        return "tidy"
    return "table"

def normalize_time_column(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    """Ensure 'time' exists and is standardized; also infer frequency."""
    if time_col not in df.columns:
        return df
    s = df[time_col].astype(str)
    freq = None
    if s.str.fullmatch(r"\d{4}").all():  # annual
        freq = "A"
    elif s.str.fullmatch(r"\d{4}-Q[1-4]").all():
        freq = "Q"
    elif s.str.fullmatch(r"\d{4}-M\d{2}").all():
        freq = "M"
    df[time_col] = s
    df.attrs["time_freq"] = freq
    return df
