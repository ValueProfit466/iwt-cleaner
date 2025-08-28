from __future__ import annotations
from iwt_cleaner.io_prompts import prompt_io_and_paths
from iwt_cleaner.pipeline import run_pipeline
from iwt_cleaner.cleaner import CleaningConfig

def main():
    spec, sheet, out_path, ts_label, out_dir = prompt_io_and_paths()
    results, manifest = run_pipeline(
        input_spec_or_path=spec,
        output_path=out_path,
        source_sheet=sheet,
        config=CleaningConfig(),
        verbose=False,
        export_parquet=True,
        profile_html=False,
    )
    print("\n" + "="*60)
    print("CLEANING COMPLETED SUCCESSFULLY")
    print("="*60)
    print(f"Input:  {spec}")
    print(f"Output: {out_path.name} in folder {out_dir.name} ({results['detail'].shape[0]} clean rows)")
    print(f"Removed: {results['totals'].shape[0]} total/subtotal rows (table mode only)")
    if "flags_summary" in results['metadata']:
        print(f"Flags: {results['metadata']['flags_summary']}")
    print("="*60)

if __name__ == "__main__":
    main()
