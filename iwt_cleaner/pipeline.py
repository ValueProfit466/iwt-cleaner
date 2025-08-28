from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import logging
from pathlib import Path

import pandas as pd

from .adapters import get_ingestor, LocalFileIngestor
from .cleaner import CleaningConfig, TableCleaner, DataProfiler
from .normalization import detect_mode, normalize_time_column
from .validators import validate_tidy
from .reporting import create_excel_report, write_manifest

FLAG_LABELS = {'p':'provisional','e':'estimate','b':'break in series','c':'confidential','d':'definition differs','f':'forecast','n':'not significant','u':'low reliability',':':'not available'}

def _setup_logger(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    return logging.getLogger(__name__)

def _eurostat_enrich(df: pd.DataFrame, source_meta: Dict[str, Any]) -> pd.DataFrame:
    """Optional enrichment: attach flags summary and try codelist labels (best-effort)."""
    # Flag coverage
    if "flag" in df.columns:
        flag_counts = df["flag"].astype(str).value_counts(dropna=True).to_dict()
        df.attrs["flags_summary"] = flag_counts

    # Codelist labels (best effort)
    try:
        import eurostat # type: ignore
        ds = source_meta.get("dataset")
        for dim in ["geo","unit","na_item","s_adj","nace_r2"]:
            if dim in df.columns:
                try:
                    dic = eurostat.get_dic(ds, dim, frmt="df", lang=source_meta.get("lang","en"))
                    if isinstance(dic, pd.DataFrame) and {"code","label"} <= set(dic.columns):
                        mapper = dict(zip(dic["code"].astype(str), dic["label"].astype(str)))
                        df[f"{dim}_label"] = df[dim].astype(str).map(mapper)
                except Exception:
                    continue
    except Exception:
        pass
    return df

def _tidy_process(df: pd.DataFrame, source_meta: Dict[str, Any], config: CleaningConfig) -> Dict[str, Any]:
    logger = logging.getLogger(__name__)
    logger.info("Processing in TIDY mode")
    df = normalize_time_column(df, "time")
    # Attempt enrichment for Eurostat
    if source_meta.get("source") == "eurostat":
        df = _eurostat_enrich(df, source_meta)

    # Ensure 'value' numeric
    df["value"] = pd.to_numeric(df["value"], errors="coerce") if "value" in df.columns else df.get("value", pd.Series(dtype=float))

    # Profile
    profile_before = DataProfiler.profile_dataframe(df.copy())
    # Normalize dtypes a bit
    for c in df.select_dtypes(include="object").columns:
        # leave label columns as object; dims can be categories
        if not c.endswith("_label") and c not in ("time", "flag"):
            df[c] = df[c].astype("category")

    # Optional validation
    try:
        validate_tidy(df)
    except Exception:
        logger.warning("Validation failed; continuing with report.")

    profile_after = DataProfiler.profile_dataframe(df.copy())

    metadata = {
        "original_shape": (profile_before["row_count"], profile_before["column_count"]),
        "original_columns": list(df.columns),
        "dropped_columns": [],
        "dimensions": [c for c in df.columns if c not in ("value","flag") and not c.endswith("_label")],
        "measures": ["value"] if "value" in df.columns else [],
        "confidence_scores": {},
        "row_type_counts": {},
        "total_markers": [],
        "profile_before": profile_before,
        "profile_after": profile_after,
        "number_format": None
    }
    if hasattr(df, "attrs") and df.attrs.get("flags_summary"):
        metadata["flags_summary"] = df.attrs["flags_summary"]

    return {"detail": df, "totals": pd.DataFrame(), "metadata": metadata}

def run_pipeline(
    input_spec_or_path: str,
    output_path: Path,
    source_sheet: Optional[str] = None,
    config: Optional[CleaningConfig] = None,
    verbose: bool = False,
    export_parquet: bool = True,
    profile_html: bool = False,
    source_lang: str = "en",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Ingest → Detect mode → Process → Report.
    Returns (results, manifest_dict).
    """
    logger = _setup_logger(verbose)
    cfg = config or CleaningConfig()

    # Ingest
    ingestor = get_ingestor(input_spec_or_path)
    if isinstance(ingestor, LocalFileIngestor) and source_sheet and ingestor.sheet is None:
        ingestor.sheet = source_sheet
    df = ingestor.load()
    source_meta = ingestor.meta()

    logger.info(f"Ingested {len(df)} rows × {len(df.columns)} cols from source={source_meta.get('source')}")
    mode = detect_mode(df)

    # Route: tidy vs table
    if mode == "tidy":
        results = _tidy_process(df, source_meta, cfg)
    else:
        cleaner = TableCleaner(df, cfg)
        results = cleaner.clean()

    # Write Excel report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    create_excel_report(str(output_path), results, mode, source_meta)
    logger.info(f"Excel report written to: {output_path}")

    # Optional Parquet for downstream modeling
    if export_parquet:
        parquet_path = output_path.with_suffix(".parquet")
        results["detail"].to_parquet(parquet_path, index=False)
        logger.info(f"Parquet written to: {parquet_path}")

    # Optional profiling
    if profile_html:
        try:
            from ydata_profiling import ProfileReport
            prof = ProfileReport(results["detail"], title="Data Profiling Report", minimal=True)
            html_path = output_path.with_suffix(".profile.html")
            prof.to_file(html_path)
            logger.info(f"Profiling report written to: {html_path}")
        except Exception as e:
            logger.warning(f"Profiling skipped: {e}")

    # Manifest
    manifest = {
        "source": source_meta,
        "mode": mode,
        "output": {
            "excel": str(output_path),
            "parquet": str(output_path.with_suffix('.parquet')) if export_parquet else None
        },
        "shapes": {
            "original": results["metadata"]["original_shape"],
            "final": (results["metadata"]["profile_after"]["row_count"], results["metadata"]["profile_after"]["column_count"]),
        },
        "columns": results["metadata"]["original_columns"],
    }
    write_manifest(output_path.parent, manifest)

    return results, manifest
