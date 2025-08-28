from __future__ import annotations
import logging, re, warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pandas.api.types import is_categorical_dtype, is_numeric_dtype # type: ignore

# ---- Config -----------------------------------------------------------------

@dataclass
class CleaningConfig:
    dims: Optional[List[str]] = None
    measures: Optional[List[str]] = None
    total_markers: List[str] = None # type: ignore
    keep_constants: bool = False
    decimal: Optional[str] = None
    thousands: Optional[str] = None
    min_confidence: float = 0.7  # Minimum confidence for auto-detection
    def __post_init__(self):
        if self.total_markers is None:
            self.total_markers = [
                "Totaal","Total","Alle","Alle plaatsen","All","Grand total","Subtotal","Totalen","Sum","Summary","Aggregate","Overall"
            ]

# ---- Profiling --------------------------------------------------------------

class DataProfiler:
    @staticmethod
    def profile_column(series: pd.Series) -> Dict[str, Any]:
        profile = {
            "name": series.name,
            "dtype": str(series.dtype),
            "null_count": series.isna().sum(),
            "null_percent": series.isna().mean() * 100,
            "unique_count": series.nunique(),
            "unique_percent": (series.nunique() / len(series) * 100) if len(series) else 0,
        }
        if is_numeric_dtype(series):
            profile.update({
                "mean": series.mean(),
                "std": series.std(),
                "min": series.min(),
                "max": series.max(),
                "zeros": (series == 0).sum(),
                "negative_count": (series < 0).sum() if not series.empty else 0,
            })
        else:
            non_null = series.dropna()
            if len(non_null) > 0:
                profile["sample_values"] = non_null.astype(str).value_counts().head(5).to_dict()
                profile["avg_length"] = non_null.astype(str).str.len().mean()
        return profile

    @staticmethod
    def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
            "duplicate_rows": df.duplicated().sum(),
            "columns": [DataProfiler.profile_column(df[c]) for c in df.columns],
        }

# ---- Number parsing ----------------------------------------------------------

class NumberParser:
    def __init__(self, decimal: Optional[str] = None, thousands: Optional[str] = None):
        self.decimal = decimal
        self.thousands = thousands
        self._detected_format: Optional[Tuple[str, str]] = None

    def detect_format(self, sample: pd.Series) -> Tuple[str, str]:
        if self._detected_format:
            return self._detected_format
        str_sample = sample.dropna().astype(str).head(100)
        comma_as_decimal, dot_as_decimal = 0, 0
        for val in str_sample:
            v = val.strip()
            if re.match(r'^\d{1,3}(\.\d{3})+,\d+$', v): comma_as_decimal += 1
            elif re.match(r'^\d{1,3}(,\d{3})+\.\d+$', v): dot_as_decimal += 1
            elif ',' in v and '.' not in v and re.match(r'^\d+,\d{1,2}$', v): comma_as_decimal += 1
            elif '.' in v and ',' not in v and re.match(r'^\d+\.\d{1,2}$', v): dot_as_decimal += 1
        self._detected_format = (',', '.') if comma_as_decimal > dot_as_decimal else ('.', ',')
        return self._detected_format

    def parse_number(self, value: Any) -> float:
        if value is None or (isinstance(value, float) and np.isnan(value)): return np.nan
        if isinstance(value, (int, float)) and not np.isnan(value): return float(value)
        txt = str(value).strip()
        if txt == "" or txt.lower() in {'na','n/a','null','none','-'}: return np.nan
        txt = re.sub(r'[%€$£\s]', '', txt)
        negative = False
        if txt.startswith('(') and txt.endswith(')'): negative, txt = True, txt[1:-1].strip()
        elif txt.startswith('-'): negative, txt = True, txt[1:].strip()
        if self.decimal and self.thousands:
            if self.thousands: txt = txt.replace(self.thousands, '')
            if self.decimal != '.': txt = txt.replace(self.decimal, '.')
        else:
            if ',' in txt and '.' in txt:
                if txt.rfind(',') > txt.rfind('.'): txt = txt.replace('.', '').replace(',', '.')
                else: txt = txt.replace(',', '')
            elif ',' in txt:
                parts = txt.split(',')
                txt = txt.replace(',', '.') if (len(parts) == 2 and len(parts[1]) <= 3) else txt.replace(',', '')
        try:
            val = float(txt)
            return -val if negative else val
        except ValueError:
            return np.nan

    def parse_series(self, series: pd.Series) -> pd.Series:
        if is_numeric_dtype(series): return series
        if not self.decimal and not self.thousands: self.detect_format(series)
        return series.apply(self.parse_number)

# ---- Column classification ---------------------------------------------------

class ColumnClassifier:
    def __init__(self, df: pd.DataFrame, config: CleaningConfig):
        self.df, self.config = df, config
        self.logger = logging.getLogger(__name__)

    def compute_dimension_score(self, col: str) -> float:
        s = self.df[col]; score = 0.0
        n_rows = len(self.df); nunique = s.nunique(); ratio = (nunique / n_rows) if n_rows else 0
        if ratio < 0.1: score += 0.4
        elif ratio < 0.3: score += 0.2
        if is_categorical_dtype(s) or s.dtype == 'object': score += 0.3
        if any(p in col.lower() for p in ['year','jaar','month','maand','region','gewest','category','type','group','segment','naam','name','code','id','status','rechtsvorm']): score += 0.3
        return min(score, 1.0)

    def compute_measure_score(self, col: str) -> float:
        s = self.df[col]; score = 0.0
        if is_numeric_dtype(s): score += 0.5
        else:
            sample = s.dropna().astype(str).head(100)
            patt = re.compile(r'^[\d,.\-\(\)]+$')
            numeric_looking = sample.apply(lambda x: bool(patt.match(x.strip()))).mean()
            score += float(numeric_looking) * 0.4
        if s.nunique() > len(self.df) * 0.5: score += 0.2
        if any(p in col.lower() for p in ['amount','aantal','count','sum','total','value','waarde','bedrag','price','prijs','cost','kost','revenue','omzet','quantity','volume']): score += 0.3
        return min(score, 1.0)

    def classify_columns(self) -> Tuple[List[str], List[str], Dict[str, float]]:
        conf, dims, measures = {}, [], []
        for c in self.df.columns:
            ds, ms = self.compute_dimension_score(c), self.compute_measure_score(c)
            conf[c] = max(ds, ms)
            if conf[c] < self.config.min_confidence: self.logger.warning(f"Low confidence ({conf[c]:.2f}) for column '{c}'")
            (measures if ms > ds else dims).append(c)
        return dims, measures, conf

# ---- Table Cleaner -----------------------------------------------------------

class TableCleaner:
    def __init__(self, df: pd.DataFrame, config: CleaningConfig):
        self.df, self.config = df, config
        self.logger = logging.getLogger(__name__)
        self.parser = NumberParser(config.decimal, config.thousands)

    def identify_constant_columns(self) -> List[str]:
        const_cols = []
        for col in self.df.columns:
            vals = self.df[col].dropna().unique()
            if len(vals) <= 1:
                const_cols.append(col)
                if len(vals) == 1:
                    self.logger.info(f"Constant column '{col}' with value: {vals[0]}")
        return const_cols

    def classify_rows(self, dims: List[str]) -> pd.DataFrame:
        markers_lower = {str(m).strip().lower() for m in self.config.total_markers}
        classifications = []
        for idx, row in self.df.iterrows():
            dim_statuses = []
            for dim in dims:
                if dim not in self.df.columns: dim_statuses.append('missing'); continue
                val = row[dim]
                if pd.isna(val) or str(val).strip() == '': dim_statuses.append('empty')
                elif str(val).strip().lower() in markers_lower: dim_statuses.append('marker')
                else: dim_statuses.append('value')
            empty_or_marker = sum(1 for s in dim_statuses if s in ['empty','marker'])
            row_type = 'detail' if empty_or_marker == 0 else ('grand_total' if empty_or_marker == len(dim_statuses) else 'subtotal')
            classifications.append({'index': idx, 'row_type': row_type, 'dim_statuses': dim_statuses, 'total_level': empty_or_marker})
        return pd.DataFrame(classifications)

    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            dt = df[col].dtype
            try:
                if 'int' in str(dt):
                    df[col] = pd.to_numeric(df[col], downcast='integer')
                elif 'float' in str(dt):
                    if df[col].dropna().apply(lambda x: x == int(x)).all():
                        df[col] = df[col].astype('Int64')
                    else:
                        df[col] = pd.to_numeric(df[col], downcast='float')
            except Exception:
                pass
        return df

    def clean(self) -> Dict[str, Any]:
        self.logger.info(f"Starting cleaning on {len(self.df)} rows, {len(self.df.columns)} columns")
        original_shape = self.df.shape
        original_columns = list(self.df.columns)
        profile_before = DataProfiler.profile_dataframe(self.df)

        const_cols = self.identify_constant_columns()
        if const_cols and not self.config.keep_constants:
            self.logger.info(f"Dropping {len(const_cols)} constant columns")
            self.df = self.df.drop(columns=const_cols)

        if not self.config.dims or not self.config.measures:
            classifier = ColumnClassifier(self.df, self.config)
            dims, measures, confidence = classifier.classify_columns()
            if self.config.dims: dims = self.config.dims
            if self.config.measures: measures = self.config.measures
            self.logger.info(f"Identified {len(dims)} dimensions, {len(measures)} measures")
        else:
            dims, measures, confidence = self.config.dims, self.config.measures, {}

        row_classifications = self.classify_rows(dims)
        row_type_counts = row_classifications['row_type'].value_counts().to_dict()
        self.df['_row_type'] = row_classifications['row_type'].values
        self.df['_total_level'] = row_classifications['total_level'].values

        detail_df = self.df[self.df['_row_type'] == 'detail'].copy()
        totals_df = self.df[self.df['_row_type'] != 'detail'].copy()
        detail_df = detail_df.drop(columns=['_row_type','_total_level'])

        for m in measures:
            if m in detail_df.columns:
                detail_df[m] = self.parser.parse_series(detail_df[m])

        detail_df = self._optimize_dtypes(detail_df)
        profile_after = DataProfiler.profile_dataframe(detail_df)

        return {
            'detail': detail_df,
            'totals': totals_df,
            'metadata': {
                'original_shape': original_shape,
                'original_columns': original_columns,
                'dropped_columns': const_cols if not self.config.keep_constants else [],
                'dimensions': dims,
                'measures': measures,
                'confidence_scores': confidence,
                'row_type_counts': row_type_counts,
                'total_markers': self.config.total_markers,
                'profile_before': profile_before,
                'profile_after': profile_after,
                'number_format': self.parser._detected_format
            }
        }
