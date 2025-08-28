from __future__ import annotations
import argparse
from pathlib import Path
from iwt_cleaner.pipeline import run_pipeline
from iwt_cleaner.cleaner import CleaningConfig

def main():
    ap = argparse.ArgumentParser(description="IWT Cleaner – source-agnostic pipeline")
    ap.add_argument("--in", dest="input_spec", required=True, help="File path or adapter spec (file:, eurostat:, sdmx:)")
    ap.add_argument("--sheet", help="Sheet name (Excel only, when using file:)")
    ap.add_argument("--out", dest="output", required=True, help="Output .xlsx path")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-parquet", action="store_true")
    ap.add_argument("--profile", action="store_true", help="Generate HTML profile (if ydata-profiling installed)")

    args = ap.parse_args()
    out_path = Path(args.output)

    run_pipeline(
        input_spec_or_path=args.input_spec,
        output_path=out_path,
        source_sheet=args.sheet,
        config=CleaningConfig(),
        verbose=args.verbose,
        export_parquet=not args.no_parquet,
        profile_html=args.profile,
    )

if __name__ == "__main__":
    main()
