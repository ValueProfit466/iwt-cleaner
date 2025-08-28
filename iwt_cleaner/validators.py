from __future__ import annotations
import logging
import pandas as pd

def validate_tidy(df: pd.DataFrame) -> None:
    """
    Optional Pandera validation for tidy frames: ['value'] numeric allowed NA,
    'time' present. Silently no-op if pandera isn't installed.
    """
    try:
        import pandera.pandas as pa
        import pandera.typing as pat

        class TidySchema(pa.DataFrameModel):
            time: pat.Series[str]
            value: pat.Series[float] = pa.Field(nullable=True)
            class Config: coerce = True

        TidySchema.validate(df, lazy=True)
    except ImportError:
        logging.getLogger(__name__).info("Pandera not installed; skipping validation.")
    except Exception as e:
        logging.getLogger(__name__).error(f"Validation failed: {e}")
        raise
