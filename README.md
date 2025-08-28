# IWT Cleaner (Source-Agnostic)

A modular, production-grade cleaner that handles:

- **Local files** (Excel/CSV cross-tabs → “table mode” with totals detection and number parsing),
- **Eurostat datasets** via `eurostat` (tidy data with flags & codelists),
- **SDMX** via `pandasdmx`.

It then generates a multi-sheet **Excel report**, an optional **Parquet** extract, and a **manifest.json**.

> This codebase refactors and generalizes your original `clean_multiindex_table.py` while preserving its core table-cleaning logic. :contentReference[oaicite:1]{index=1}

---

## Quickstart

### Interactive (prompts + timestamped folder/file names)

```bash
python scripts/run_interactive.py
# Then follow prompts:
#  - Enter input (e.g., 'mydata.xlsx' or 'eurostat:estat_iww_go_atygo?flags=1&geo=BE,NL&startPeriod=2015')
#  - If Excel, provide sheet name (or Enter for first)
```
