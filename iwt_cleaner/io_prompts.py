from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import os

def prompt_io_and_paths() -> Tuple[str, Optional[str], Path, str, Path]:
    """
    Ask the user for the input spec (file or adapter spec), prompt for sheet if Excel,
    and prepare the output folder+filename per policy:

    Output folder: cleaned_<HH:MM:SS DDMMYY> (':' replaced with '-' on Windows)
    Output file:   <input_stem>_<HH:MM:SS DDMMYY>.xlsx
    Returns:
      (input_spec_or_path, sheet_name, output_path, canonical_ts, out_dir)
    """
    script_dir = Path(__file__).resolve().parent.parent

    spec = input("Enter input (file name in this directory OR a source spec like 'eurostat:DS_CODE?...'): ").strip().strip('"').strip("'")

    sheet_name: Optional[str] = None
    # If it's a local file path (no ':') we can ask sheet for Excel; if csv, keep prompt but it's a no-op
    if ":" not in spec:
        p = (script_dir / spec).resolve()
        if not p.exists(): raise FileNotFoundError(f"File not found next to scripts: {p}")
        if p.suffix.lower() in {'.xlsx','.xlsm','.xlsb','.xls'}:
            s = input("Excel detected. Sheet name (Enter for first): ").strip()
            sheet_name = s or None
        elif p.suffix.lower() == '.csv':
            input("CSV detected. (No sheets). Press Enter to continue: ")
        input_stem = p.stem
    else:
        # For adapters, try to derive a stem
        input_stem = spec.split("?",1)[0].split(":")[1].replace("/", "_").replace(".", "_")

    ts_label = datetime.now().strftime("%H:MM:SS %d%m%y")  # intentionally HH:MM:SS DDMMYY-like
    # Correct hour formatting to 24h
    ts_label = datetime.now().strftime("%H:%M:%S %d%m%y")
    ts_fs = ts_label.replace(":", "-") if os.name == 'nt' else ts_label

    out_dir = (script_dir / f"cleaned_{ts_fs}")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{input_stem}_{ts_fs}.xlsx"
    return spec, sheet_name, out_path, ts_label, out_dir
