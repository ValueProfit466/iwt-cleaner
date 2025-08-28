from __future__ import annotations
from typing import Any, Dict
from pathlib import Path
import json
import pandas as pd

FLAG_LABELS = {
    'p': 'provisional', 'e': 'estimate', 'b': 'break in series',
    'c': 'confidential', 'd': 'definition differs', 'f': 'forecast',
    'n': 'not significant', 'u': 'low reliability', ':': 'not available'
}

def create_excel_report(output_path: str, results: Dict[str, Any], mode: str, source_meta: Dict[str, Any]) -> None:
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        workbook = writer.book
        # README
        readme_df = pd.DataFrame({'README': [generate_readme(results['metadata'], mode, source_meta)]})
        readme_df.to_excel(writer, sheet_name='README', index=False)

        # Clean Data
        results['detail'].to_excel(writer, sheet_name='Clean Data', index=False)

        # Dropped Totals
        if 'totals' in results and isinstance(results['totals'], pd.DataFrame) and not results['totals'].empty:
            results['totals'].to_excel(writer, sheet_name='Dropped Totals', index=False)

        # Data Quality
        quality_df = create_quality_report(results['metadata'])
        quality_df.to_excel(writer, sheet_name='Data Quality', index=False)

        # Column Info
        col_meta = create_column_metadata(results['metadata'])
        col_meta.to_excel(writer, sheet_name='Column Info', index=False)

        for sheet in writer.sheets.values():
            sheet.set_column('A:Z', 18)

def generate_readme(metadata: Dict, mode: str, source_meta: Dict[str, Any]) -> str:
    lines = [
        "DATA CLEANING REPORT",
        "=" * 50,
        "",
        "PIPELINE SUMMARY",
        "-" * 20,
        f"Mode: {mode}",
        f"Source: {source_meta.get('source')}",
    ]
    if source_meta.get("source") == "eurostat":
        lines += [
            f"Dataset: {source_meta.get('dataset')}",
            f"Filters: {source_meta.get('filters')}",
            f"Flags requested: {source_meta.get('flags')}",
        ]
    lines += [
        "",
        "SHAPES",
        "-" * 20,
        f"Original: {metadata['original_shape'][0]} rows × {metadata['original_shape'][1]} cols",
        f"Final:    {metadata['profile_after']['row_count']} rows × {metadata['profile_after']['column_count']} cols",
        f"Memory:   {metadata['profile_before']['memory_usage_mb']:.2f} MB → {metadata['profile_after']['memory_usage_mb']:.2f} MB",
        "",
        "ROW CLASSIFICATION (table mode only)",
        "-" * 20,
    ]
    for k, v in metadata.get('row_type_counts', {}).items():
        lines.append(f"• {k}: {v} rows")
    lines += [
        "",
        "CONFIGURATION / DETECTIONS",
        "-" * 20,
        f"• Dropped constant columns: {len(metadata.get('dropped_columns', []))}",
        f"• Dimensions: {len(metadata.get('dimensions', []))}",
        f"• Measures: {len(metadata.get('measures', []))}",
        f"• Number format detected: {metadata.get('number_format')}",
    ]
    if "flags_summary" in metadata:
        lines += ["", "FLAGS (Eurostat)", "-" * 20]
        for k, v in metadata["flags_summary"].items():
            lines.append(f"• {k}: {v}")
        lines += ["Legend: " + ", ".join(f"{k}={FLAG_LABELS.get(k,k)}" for k in sorted(metadata["flags_summary"]))]

    lines += ["", "COLUMNS", "-" * 20]
    for dim in metadata.get('dimensions', []):
        lines.append(f"• DIM: {dim} (confidence: {metadata['confidence_scores'].get(dim, 0):.2%})")
    for meas in metadata.get('measures', []):
        lines.append(f"• MEA: {meas} (confidence: {metadata['confidence_scores'].get(meas, 0):.2%})")

    return "\n".join(lines)

def create_quality_report(metadata: Dict) -> pd.DataFrame:
    before, after = metadata['profile_before'], metadata['profile_after']
    rows = [
        {"Metric": "Total Rows", "Before": before['row_count'], "After": after['row_count'], "Change": after['row_count'] - before['row_count']},
        {"Metric": "Total Columns", "Before": before['column_count'], "After": after['column_count'], "Change": after['column_count'] - before['column_count']},
        {"Metric": "Memory Usage (MB)", "Before": f"{before['memory_usage_mb']:.2f}", "After": f"{after['memory_usage_mb']:.2f}", "Change": f"{after['memory_usage_mb']-before['memory_usage_mb']:.2f}"},
        {"Metric": "Duplicate Rows", "Before": before['duplicate_rows'], "After": after['duplicate_rows'], "Change": after['duplicate_rows'] - before['duplicate_rows']},
    ]
    return pd.DataFrame(rows)

def create_column_metadata(metadata: Dict) -> pd.DataFrame:
    out = []
    for col_profile in metadata['profile_after']['columns']:
        name = col_profile['name']
        row = {
            'Column': name,
            'Type': 'Dimension' if name in metadata.get('dimensions', []) else ('Measure' if name in metadata.get('measures', []) else 'Other'),
            'Data Type': col_profile['dtype'],
            'Null %': f"{col_profile['null_percent']:.1f}%",
            'Unique Values': col_profile['unique_count'],
            'Confidence': f"{metadata.get('confidence_scores', {}).get(name, 0):.2%}"
        }
        if 'mean' in col_profile:
            row.update({'Mean': f"{col_profile['mean']:.2f}" if col_profile['mean']==col_profile['mean'] else 'N/A', 'Min': col_profile['min'], 'Max': col_profile['max']})
        out.append(row)
    return pd.DataFrame(out)

def write_manifest(out_dir: Path, manifest: Dict[str, Any]) -> None:
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
