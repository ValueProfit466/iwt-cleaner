# IWT Cleaner — Zero‑Coding Quick Start

**What this tool does (in plain English):**
You give it a spreadsheet or a CSV/TSV file (or ask it to fetch public data from Eurostat). It cleans the table, removes totals/subtotals, fixes number formats, and gives you a tidy **Excel report** you can use right away. No coding required.

---

## 1) What you’ll install (once)

> Time commitment: \~15 minutes. You only do this the first time.

**On Windows 10/11, macOS, or Linux:**

1. **Python (3.11 or newer)**

   * Install from the official Python website (select “Add Python to PATH” on Windows).
   * Verify in a terminal:

     * **Windows (PowerShell):** `py --version`
     * **macOS/Linux:** `python3 --version`

2. **VS Code (Visual Studio Code)**

   * After installing, open VS Code and install these extensions:

     * **Python** (Microsoft)
     * **Pylance** (Microsoft)
     * *(Optional)* **Jupyter** (Microsoft), if you like notebooks.

3. **Git**

   * Install Git (the standard installer is fine).
   * Verify in a terminal: `git --version`

> Tip (VS Code): Open the **Command Palette** with `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS). You’ll use it to pick the Python interpreter later.

---

## 2) Get the project onto your computer

Open a terminal and run:

```bash
git clone https://github.com/ValueProfit466/iwt-cleaner.git
cd iwt-cleaner
```

Then open the folder in VS Code:

* From a terminal: `code .`
* Or in VS Code: File → Open Folder → choose `iwt-cleaner`.

---

## 3) Create your Python environment (Core)

This project uses a **clean, separate environment** so your main system stays untouched.

> The “Core” environment runs local files and the **Eurostat** adapter. It’s the right choice for 90% of users. (The SDMX adapter is advanced and uses a different environment; see Section 6.)

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv-core
.\.venv-core\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv-core
source .venv-core/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Behind the scenes, `requirements.txt` sets up the modern data stack for this project (Pandas 2.2+, Pydantic v2, optional profiling), and intentionally avoids SDMX‑specific packages to keep things simple/stable in the Core workflow.&#x20;

**Pick your interpreter in VS Code:**
Command Palette → “**Python: Select Interpreter**” → choose the one inside **`.venv-core`**.

---

## 4) Run it the easy way (no coding)

### Option A — Interactive (recommended for beginners)

From VS Code’s integrated terminal (or any terminal) **inside the activated `.venv-core`**:

```bash
python scripts/run_interactive.py
```

You’ll be prompted for:

* **Input**:

  * Type a file name that’s in the project folder (e.g., `mydata.xlsx`, `mydata.csv`, `mydata.tsv`).
  * Or use a Eurostat spec (e.g., `eurostat:estat_iww_go_atygo?flags=1&geo=BE,NL&startPeriod=2015`).
* **Sheet name** (only if you selected an Excel file). Press Enter to use the first sheet.

**Output:**
The tool creates a new subfolder like `cleaned_14:03:27 280825` (time+date) and writes:

* An **Excel report** (multi-sheet) summarizing the cleaned data
* A **Parquet** file (for advanced analytics; optional)
* A `manifest.json` (what was run, when, with what settings)

> Windows note: if you see dashes in the time (`14-03-27`), that’s normal—Windows doesn’t allow colons in file names. The manifest keeps the original timestamp.

### Option B — Command line (for the confident)

**Local file:**

```bash
python scripts/cli.py --in "file:mydata.xlsx?sheet=Data" --out out.xlsx
```

**Eurostat pull:**

```bash
python scripts/cli.py --in "eurostat:estat_iww_go_atygo?flags=1&geo=BE,DE,NL&startPeriod=2015" --out iww_cleaned.xlsx
```

---

## 5) Where to put your source data

* Save your **.xlsx / .csv / .tsv** files directly in the project folder (same level as `scripts/`).
* Use the interactive runner (Section 4) and just type the file name when prompted.
* The output will be written to a fresh `cleaned_<timestamp>` folder each run, so nothing gets overwritten by accident.

---

## 6) (Advanced) SDMX mode — only if you *need* it

Some users prefer the **SDMX** route (using `pandasdmx`). That library requires older core packages, so it lives in a **separate environment** to avoid conflicts.

### Create the SDMX environment

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv-sdmx
.\.venv-sdmx\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-sdmx.txt
```

**macOS / Linux:**

```bash
python3 -m venv .venv-sdmx
source .venv-sdmx/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-sdmx.txt
```

Run SDMX adapter:

```bash
python scripts/cli.py --in "sdmx:ESTAT/estat_iww_go_atygo?key=geo.BE+NL&startPeriod=2015" --out iww_sdmx.xlsx --no-parquet
```

> Why separate? The SDMX stack pins different versions (e.g., Pydantic v1, Pandas <2.1). Keeping it isolated prevents dependency conflicts and keeps your Core workflow stable. Your repo already reflects this split via `requirements.txt` (Core) and `requirements-sdmx.txt` (SDMX). &#x20;

---

## 7) Important commands (cheat sheet)

**Activate environment**

* Windows: `.\.venv-core\Scripts\Activate.ps1`
* macOS/Linux: `source .venv-core/bin/activate`

**Install dependencies**

```bash
pip install -r requirements.txt
```

**Run the interactive tool (no coding)**

```bash
python scripts/run_interactive.py
```

**Run with explicit inputs and outputs**

```bash
python scripts/cli.py --in "file:mydata.xlsx?sheet=Data" --out out.xlsx
```

**Update packages (optional)**

```bash
pip install --upgrade -r requirements.txt
```

**Deactivate environment**

```bash
deactivate
```

---

## 8) Troubleshooting (fast fixes)

* **“Python not found”**

  * Windows: use `py` instead of `python`.
  * macOS/Linux: use `python3` instead of `python`.

* **PowerShell won’t activate venv (Execution Policy)**

  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\.venv-core\Scripts\Activate.ps1
  ```

* **VS Code still shows the wrong interpreter**

  * Command Palette → “Python: Select Interpreter” → choose `.venv-core`.

* **Pip install fails behind a proxy**

  * Ask IT for your proxy settings, then:
    `pip install --proxy http://user:pass@proxy:port -r requirements.txt`

* **You installed both Core and SDMX into the same env**

  * Delete that folder and recreate **two** separate envs (`.venv-core`, `.venv-sdmx`).
  * Reinstall with their respective requirement files. &#x20;

---

## 9) What you’ll see in the Excel report

* **README sheet**: what was done, shapes before/after, key statistics.
* **Clean Data**: the usable output.
* **Dropped Totals**: anything identified as totals/subtotals (for audit).
* **Data Quality** & **Column Info**: quick diagnostics and column summaries.

This structure is baked into the project so results are consistent across datasets.&#x20;

---

## 10) Good practices (optional but recommended)

* Keep **data files out of Git** (large, private, or changing often).
* Re‑run the cleaner whenever you receive new files; each run produces a dated folder.
* If you need to share the output, send the Excel report from the `cleaned_<timestamp>` folder.

---

### You’re done

You can now clean local files or fetch from Eurostat with **no coding**. If you need help picking the right input method for a specific dataset (e.g., modal split, IWW freight volumes), start the **interactive** runner and follow the prompts.
