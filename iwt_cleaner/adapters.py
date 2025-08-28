from __future__ import annotations
from typing import Dict, Any, Optional
import re
import pandas as pd
from pathlib import Path
from urllib.parse import parse_qs

# ---- Registry Pattern -------------------------------------------------------

class BaseIngestor:
    def load(self) -> pd.DataFrame: ...
    def meta(self) -> Dict[str, Any]: return {}

REGISTRY: Dict[str, type[BaseIngestor]] = {}

def register(name: str):
    def _wrap(cls):
        REGISTRY[name] = cls
        return cls
    return _wrap

def get_ingestor(spec: str, **kwargs) -> BaseIngestor:
    """
    Spec examples:
      - "file:mydata.xlsx?sheet=Sheet1"
      - "file:mydata.csv?encoding=utf-8"
      - "eurostat:GOV_10DD_SLGD?flags=1&startPeriod=2015&geo=BE,NL"
      - "sdmx:ESTAT/UNE_RT_A?geo=BE+NL&startPeriod=2015"
    """
    if ":" not in spec:  # fallback: treat as local path
        return LocalFileIngestor(spec, **kwargs)
    kind, rest = spec.split(":", 1)
    if kind not in REGISTRY:
        raise ValueError(f"Unknown source '{kind}'. Registered: {list(REGISTRY)}")
    return REGISTRY[kind](rest, **kwargs) # type: ignore

# ---- Local File Adapter -----------------------------------------------------

@register("file")
class LocalFileIngestor(BaseIngestor):
    def __init__(self, path_query: str, default_encoding="utf-8"):
        path, q = (path_query.split("?", 1)+[""])[:2]
        self.path = Path(path).expanduser()
        self.params = dict((k, v[0]) for k, v in parse_qs(q).items())
        self.encoding = self.params.get("encoding", default_encoding)
        self.sheet = self.params.get("sheet")
    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"Input file not found: {self.path}")
        sfx = self.path.suffix.lower()
        if sfx in (".xlsx", ".xlsm", ".xlsb", ".xls"):
            return pd.read_excel(self.path, sheet_name=self.sheet or 0)
        elif sfx in (".csv", ".tsv", ".txt"):
            sep = "\t" if sfx == ".tsv" else ","
            try:
                return pd.read_csv(self.path, sep=sep, encoding=self.encoding, engine="pyarrow")
            except Exception:
                return pd.read_csv(self.path, sep=sep, encoding=self.encoding)
        else:
            raise ValueError(f"Unsupported extension: {sfx}")
    def meta(self) -> Dict[str, Any]:
        return {"source": "file", "path": str(self.path), "sheet": self.sheet, "encoding": self.encoding}

# ---- Eurostat Adapter -------------------------------------------------------

@register("eurostat")
class EurostatIngestor(BaseIngestor):
    """
    Uses 'eurostat' Python package. Returns a tidy-ish dataframe:
    dims + ['time', 'value'] (+ optional 'flag').
    If data are wide by period (e.g., '2019','2020' or '2019_value','2019_flag'),
    we reshape to long.
    """
    def __init__(self, code_query: str, lang="en"):
        code, q = (code_query.split("?", 1)+[""])[:2]
        self.code = code
        self.params_raw = dict((k, v) for k, v in parse_qs(q).items())  # values are lists
        # flags=1 (default off), lang pass-through (used for codelists in pipeline)
        self.flags = str(self.params_raw.get("flags", ["0"])[0]).lower() in ("1", "true", "yes")
        self.lang = self.params_raw.get("lang", [lang])[0]
        # Build eurostat filter dict: accept simple comma lists
        self.filter_pars: Dict[str, Any] = {}
        for k, vs in self.params_raw.items():
            if k in ("flags", "lang"): 
                continue
            v = vs[0]
            self.filter_pars[k] = [x for x in v.replace(" ", "").split(",") if x] if "," in v else v

    def load(self) -> pd.DataFrame:
        import eurostat # type: ignore
        import pandas as pd, re

        # Pull data
        try:
            df = eurostat.get_data_df(self.code, self.flags, self.filter_pars or None, verbose=False)
        except TypeError:
            df = eurostat.get_data_df(self.code, flags=self.flags, filter_pars=self.filter_pars or None)

        if df is None:
            raise ValueError(f"No data returned for code '{self.code}' with filters {self.filter_pars}")

        # If already tidy (has 'time' and maybe 'values'/'value'), normalize
        cols = [str(c) for c in df.columns]
        if "time" in cols and ("value" in cols or "values" in cols):
            if "values" in df.columns:
                df = df.rename(columns={"values": "value"})
            return df

        # Otherwise, detect period columns and melt
        id_vars = []
        time_cols = []
        value_cols = []
        flag_cols = []

        period_pat = re.compile(r"^\d{4}(|-Q[1-4]|-M\d{2})$")
        v_pat = re.compile(r"^\d{4}(|-Q[1-4]|-M\d{2})\s*_value$")
        f_pat = re.compile(r"^\d{4}(|-Q[1-4]|-M\d{2})\s*_flag$")

        for c in df.columns:
            s = str(c)
            if period_pat.match(s):
                time_cols.append(s)
            elif v_pat.match(s):
                value_cols.append(s)
            elif f_pat.match(s):
                flag_cols.append(s)
            else:
                id_vars.append(s)

        if value_cols:
            # collapse paired value/flag columns into long
            long_list = []
            for vcol in value_cols:
                base = re.sub(r"\s*_value$", "", vcol)
                fcol = next((f for f in flag_cols if f.startswith(base)), None)
                tmp = df[id_vars + [vcol] + ([fcol] if fcol else [])].copy()
                tmp.rename(columns={vcol: "value"}, inplace=True)
                if fcol:
                    tmp.rename(columns={fcol: "flag"}, inplace=True)
                tmp["time"] = base
                long_list.append(tmp)
            out = pd.concat(long_list, ignore_index=True)
            return out[id_vars + ["time", "value"] + (["flag"] if "flag" in out.columns else [])]

        if time_cols:
            out = df.melt(id_vars=id_vars, value_vars=time_cols, var_name="time", value_name="value")
            return out

        # As a final fallback, just return what we got
        return df

    def meta(self) -> Dict[str, Any]:
        return {"source": "eurostat", "dataset": self.code, "filters": self.filter_pars, "flags": self.flags, "lang": self.lang}

# ---- SDMX Adapter (optional, for completeness) ------------------------------

@register("sdmx")
class SDMXIngestor(BaseIngestor):
    """
    spec: sdmx:ESTAT/DS_CODE?key=geo.BE+NL&startPeriod=2015
    """
    def __init__(self, path_query: str):
        flow_key, q = (path_query.split("?", 1)+[""])[:2]
        self.agency, self.flow = flow_key.split("/", 1) if "/" in flow_key else ("ESTAT", flow_key)
        self.params = dict((k, v[0]) for k, v in parse_qs(q).items())
    def load(self) -> pd.DataFrame:
        import pandasdmx as sdmx
        req = sdmx.Request(self.agency)
        kw = {}
        if "key" in self.params:
            kw["key"] = self.params["key"]
        if "startPeriod" in self.params:
            kw["params"] = {"startPeriod": self.params["startPeriod"], **({"endPeriod": self.params["endPeriod"]} if "endPeriod" in self.params else {})}
        ds = req.data(self.flow, **kw)
        df = ds.to_pandas()
        df = df.reset_index()
        if "TIME_PERIOD" in df.columns:
            df = df.rename(columns={"TIME_PERIOD": "time", 0: "value"})
        elif "time" not in df.columns and "obsTime" in df.columns:
            df = df.rename(columns={"obsTime": "time", "obsValue": "value"})
        return df
    def meta(self) -> Dict[str, Any]:
        return {"source": "sdmx", "agency": self.agency, "flow": self.flow, "params": self.params}
