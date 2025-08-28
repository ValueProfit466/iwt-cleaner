from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from datetime import datetime
import os
import sys
import textwrap

# ---------------------------------
# Small utilities (pure Python)
# ---------------------------------

def _windows_safe(s: str) -> str:
    """Replace ':' with '-' on Windows filesystems."""
    return s.replace(":", "-") if os.name == "nt" else s

def _prompt_int(name: str) -> Optional[int]:
    """Prompt for an optional year; returns None if blank/invalid."""
    x = input(f"Optional {name} (year like 2019). Press Enter to skip: ").strip()
    if not x:
        return None
    try:
        return int(x)
    except ValueError:
        print(f"'{x}' is not a valid year. Skipping {name}.")
        return None

def _print_block(title: str, body: str) -> None:
    print("\n" + title)
    print("-" * len(title))
    print(body)

def _print_kv_rows(rows: List[Tuple[str, str]], left="Code", right="Description", width=90) -> None:
    """Pretty print two-column mappings in a compact, wrapped style."""
    print(f"{left:>12}  {right}")
    print(f"{'-'*12}  {'-'*(max(12, width-16))}")
    for k, v in rows:
        if v is None:
            v = ""
        wrapped = textwrap.wrap(str(v), width=width-16) or [""]
        print(f"{k:>12}  {wrapped[0]}")
        for cont in wrapped[1:]:
            print(f"{'':>12}  {cont}")

# ---------------------------------
# Eurostat-guided builder
# ---------------------------------

def _show_dataset_dictionary(code: str, eurostat) -> Dict[str, Dict[str, str]]:
    """
    Print the dataset-level dictionary: parameter code, name, description.
    Returns a quick lookup: {par_code: {"name": ..., "desc": ...}}
    """
    try:
        dic = eurostat.get_dic(code)
    except Exception as e:
        _print_block("Dictionary", f"Could not retrieve dictionary for '{code}': {e}")
        return {}

    lookup: Dict[str, Dict[str, str]] = {}
    rows: List[Tuple[str, str]] = []
    # Typical shape: list of (par, name, description)
    try:
        for par, name, desc in dic:
            lookup[str(par)] = {"name": str(name), "desc": "" if desc is None else str(desc)}
            rows.append((str(par), f"{name} — {desc if desc else ''}".strip()))
    except Exception:
        # Fallback: print raw object
        _print_block("Dictionary (raw)", str(dic))
        return lookup

    _print_block("Dataset dictionary (parameters)", "")
    _print_kv_rows(rows, left="Param", right="Name — Description")
    return lookup

def _get_param_value_mapping(code: str, par: str, eurostat) -> List[Tuple[str, str]]:
    """
    Returns list of (code, label) pairs for a parameter.
    Prefers eurostat.get_dic(code, par, frmt='df') for human labels;
    falls back to get_par_values(code, par) if necessary.
    """
    try:
        import pandas as pd  # local import for robustness
    except Exception:
        pd = None

    # Preferred: labeled dictionary as DataFrame
    try:
        if pd is not None:
            df = eurostat.get_dic(code, par, frmt="df")
            if hasattr(df, "columns") and {"val", "descr"} <= set(df.columns):
                return [(str(v), "" if pd.isna(d) else str(d)) for v, d in zip(df["val"], df["descr"])]
    except Exception:
        pass

    # Fallback: raw value codes (labels=code)
    try:
        vals = eurostat.get_par_values(code, par)
        return [(str(v), str(v)) for v in vals]
    except Exception:
        return []

def _prompt_values_for_param_with_labels(code: str, par: str, eurostat) -> Optional[List[str]]:
    """
    Interactive selection for a parameter.
    - Shows a preview (first N codes with labels).
    - '?' to print the full list.
    - Enter to keep ALL (i.e., no filter for this parameter).
    Returns None for ALL; otherwise a list of selected codes.
    """
    mapping = _get_param_value_mapping(code, par, eurostat)
    if not mapping:
        print(f"\nParameter '{par}': no values retrieved; skipping filter.")
        return None

    total = len(mapping)
    preview_n = 20
    preview = mapping[:preview_n]

    print(f"\nParameter '{par}' — {total} values available.")
    _print_kv_rows(preview, left="Code", right="Label")

    while True:
        sel = input("Enter comma-separated codes, '?' to show ALL codes, or press Enter for ALL values: ").strip()
        if sel == "":
            return None
        if sel == "?":
            _print_kv_rows(mapping, left="Code", right="Label")
            continue
        chosen = [t.strip() for t in sel.split(",") if t.strip()]
        codes_set = {c for c, _ in mapping}
        invalid = [c for c in chosen if c not in codes_set]
        if invalid:
            print(f"⚠️  Ignoring invalid codes: {', '.join(invalid)}")
        chosen = [c for c in chosen if c in codes_set]
        if chosen:
            return list(dict.fromkeys(chosen))  # preserve order, drop dups
        print("No valid codes entered. Try again, '?' to list all, or Enter for ALL.")

def _build_eurostat_spec_interactive(script_dir: Path) -> Tuple[str, Optional[str], Path, str, Path]:
    """
    Guided Eurostat mode with full dictionary & labeled parameter values.
    1) Ask dataset code
    2) Show dataset dictionary (param names & descriptions)
    3) Discover parameters and gather optional filters per parameter
    4) Ask startPeriod/endPeriod, flags, language
    5) Build 'eurostat:CODE?...' spec
    6) Create timestamped output paths
    """
    try:
        import eurostat
    except ImportError:
        print("The 'eurostat' package is not installed in this environment.\n"
              "Install it with: pip install eurostat")
        raise

    code = input("Enter Eurostat dataset code (e.g., IWW_GO_ATYGO): ").strip()
    if not code:
        raise ValueError("A dataset code is required for Eurostat guided mode.")

    # 2) Show dataset dictionary (param -> name & description)
    dic_lookup = _show_dataset_dictionary(code, eurostat)

    # 3) List parameters then prompt filters
    try:
        pars = list(eurostat.get_pars(code))
    except Exception as e:
        _print_block("Parameters", f"Could not retrieve parameters for dataset '{code}': {e}")
        raise

    _print_block("Parameters detected", ", ".join(pars) if pars else "(none)")

    filter_pars: Dict[str, object] = {}

    # Optional time windows
    sp = _prompt_int("startPeriod")
    if sp is not None:
        filter_pars["startPeriod"] = sp
    ep = _prompt_int("endPeriod")
    if ep is not None:
        filter_pars["endPeriod"] = ep

    # Parameter-by-parameter filter selection
    for par in pars:
        name = dic_lookup.get(par, {}).get("name", "")
        desc = dic_lookup.get(par, {}).get("desc", "")
        header = f"{par} — {name}" if name else par
        if desc:
            _print_block(header, desc)
        else:
            print(f"\n{header}")

        ans = input(f"Filter by '{par}'? [Enter=yes / n=no]: ").strip().lower()
        if ans == "n":
            continue

        chosen = _prompt_values_for_param_with_labels(code, par, eurostat)
        if chosen is not None:
            filter_pars[par] = chosen

    # 4) Flags & language
    flags_in = input("\nInclude Eurostat flags? [Enter=yes / n=no]: ").strip().lower()
    flags = "0" if flags_in == "n" else "1"
    lang = input("Language for labels (en/fr/de, default=en): ").strip().lower() or "en"

    # 5) Compose eurostat spec for the pipeline
    qparts = [f"flags={flags}", f"lang={lang}"]
    for k, v in filter_pars.items():
        if isinstance(v, list):
            qparts.append(f"{k}={','.join(map(str, v))}")
        else:
            qparts.append(f"{k}={v}")
    query = "&".join(qparts)
    spec = f"eurostat:{code}?{query}"
    _print_block("Spec to be used", spec)

    # 6) Timestamped output paths
    ts_label = datetime.now().strftime("%H:%M:%S %d%m%y")  # canonical label
    ts_fs = _windows_safe(ts_label)
    out_dir = script_dir / f"cleaned_{ts_fs}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{code}_{ts_fs}.xlsx"
    return spec, None, out_path, ts_label, out_dir

# --------------------------------
# Public entry point for runners
# --------------------------------

def prompt_io_and_paths() -> Tuple[str, Optional[str], Path, str, Path]:
    """
    Interactive prompt with Eurostat guided mode first and a fallback to legacy
    local-file/raw-spec mode.

    Returns:
      (input_spec_or_path, sheet_name, output_path, canonical_ts, out_dir)
    """
    script_dir = Path(__file__).resolve().parent.parent

    print("IWT Cleaner — Interactive Input")
    print("1) Eurostat guided mode (dictionary + labeled values)")
    print("2) Local file or raw spec")
    choice = input("Choose 1 or 2 [default=1]: ").strip() or "1"

    if choice == "1":
        return _build_eurostat_spec_interactive(script_dir)

    # ---- Legacy path: local file or raw 'file:'/'eurostat:'/'sdmx:' spec ----
    spec = input("\nEnter input (file name here OR a source spec like 'eurostat:DS_CODE?...'): ").strip().strip('"').strip("'")
    sheet_name: Optional[str] = None

    if ":" not in spec:
        # Treat as a local file path adjacent to the project root
        p = (script_dir / spec).resolve()
        if not p.exists():
            raise FileNotFoundError(f"File not found next to scripts: {p}")

        if p.suffix.lower() in {".xlsx", ".xlsm", ".xlsb", ".xls"}:
            s = input("Excel detected. Sheet name (Enter for first): ").strip()
            sheet_name = s or None
        elif p.suffix.lower() in {".csv", ".tsv"}:
            input(f"{p.suffix.upper()[1:]} detected. Press Enter to continue: ")

        input_stem = p.stem
    else:
        # Spec such as 'eurostat:CODE?...' or 'file:...'
        input_stem = spec.split("?", 1)[0].split(":", 1)[1].replace("/", "_").replace(".", "_")

    ts_label = datetime.now().strftime("%H:%M:%S %d%m%y")
    ts_fs = _windows_safe(ts_label)
    out_dir = script_dir / f"cleaned_{ts_fs}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{input_stem}_{ts_fs}.xlsx"
    return spec, sheet_name, out_path, ts_label, out_dir
