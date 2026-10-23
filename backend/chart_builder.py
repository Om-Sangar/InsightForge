import numpy as np
import pandas as pd

from backend.table_builder import classify_columns, _tokens, SUM_TOKENS

MAX_CHARTS = 8


def _pretty(col: str) -> str:
    return col.replace("_", " ")


def _agg_for(num_col: str) -> str:
    # Amounts, revenue, prices etc. are summed; everything else (age, score...) is averaged
    return "sum" if _tokens(num_col) & SUM_TOKENS else "mean"


def _agg_word(agg: str) -> str:
    return "Total" if agg == "sum" else "Average"


def _detect_date_columns(df: pd.DataFrame) -> list:
    date_cols = []
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            date_cols.append(col)
            continue
        if pd.api.types.is_numeric_dtype(s):
            continue
        sample = s.dropna().astype(str).head(500)
        if len(sample) == 0:
            continue
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if parsed.notna().mean() > 0.8:
            date_cols.append(col)
    return date_cols


def classify_for_charts(df: pd.DataFrame) -> dict:
    date_cols = _detect_date_columns(df)
    cls = classify_columns(df.drop(columns=date_cols))
    cls["date"] = date_cols
    return cls


def generate_chart_suggestions(df: pd.DataFrame) -> list:
    cls = classify_for_charts(df)
    cats, nums, dates = cls["categorical"], cls["numeric"], cls["date"]

    primary_bars, other_bars, donuts, lines, hists = [], [], [], [], []

    for cat in cats:
        for num in nums:
            agg = _agg_for(num)
            spec = {
                "id": f"bar|{cat}|{num}|{agg}", "type": "bar", "x": cat, "y": num, "agg": agg,
                "title": f"{_agg_word(agg)} {_pretty(num)} by {_pretty(cat)}",
            }
            (primary_bars if agg == "sum" else other_bars).append(spec)

        if df[cat].nunique() <= 8:
            donuts.append({
                "id": f"donut|{cat}", "type": "donut", "x": cat, "y": None, "agg": "count",
                "title": f"Share of records by {_pretty(cat)}",
            })

    for date_col in dates:
        for num in nums[:2]:
            agg = _agg_for(num)
            lines.append({
                "id": f"line|{date_col}|{num}|{agg}", "type": "line", "x": date_col, "y": num, "agg": agg,
                "title": f"{_agg_word(agg)} {_pretty(num)} over time",
            })

    for num in nums[:3]:
        hists.append({
            "id": f"hist|{num}", "type": "histogram", "x": num, "y": None, "agg": "count",
            "title": f"Distribution of {_pretty(num)}",
        })

    # Mix chart types so the first screen has variety instead of eight bar charts
    ordered = (
        primary_bars[:2] + donuts[:2] + lines[:1] + hists[:1]
        + primary_bars[2:] + lines[1:] + donuts[2:] + hists[1:] + other_bars
    )
    return ordered[:MAX_CHARTS]


def build_kpis(full_df: pd.DataFrame, filtered_df: pd.DataFrame) -> list:
    # Columns are chosen from the FULL dataset so KPI labels don't change when filters are applied
    nums = classify_for_charts(full_df)["numeric"]
    kpis = [{"label": "Total records", "value": int(len(filtered_df)), "kind": "count"}]

    for num in nums[:3]:
        series = filtered_df[num].dropna()
        if series.empty:
            continue
        if _tokens(num) & SUM_TOKENS:
            kpis.append({"label": f"Total {_pretty(num)}", "value": round(float(series.sum()), 2), "kind": "sum"})
        else:
            kpis.append({"label": f"Average {_pretty(num)}", "value": round(float(series.mean()), 2), "kind": "mean"})
    return kpis


def build_filter_options(df: pd.DataFrame, max_values: int = 30) -> dict:
    options = {}
    for cat in classify_for_charts(df)["categorical"]:
        values = sorted(df[cat].dropna().astype(str).unique().tolist())
        if 1 < len(values) <= max_values:
            options[cat] = values
    return options


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    for col, values in (filters or {}).items():
        if values and col in df.columns:
            df = df[df[col].astype(str).isin([str(v) for v in values])]
    return df


def build_chart_data(df: pd.DataFrame, spec: dict) -> list:
    chart_type, x, y, agg = spec["type"], spec["x"], spec.get("y"), spec.get("agg", "count")

    if chart_type == "bar":
        if y:
            result = df.groupby(x)[y].agg(agg).dropna()
        else:
            result = df[x].value_counts()
        result = result.sort_values(ascending=False).head(15)
        return [{"x": str(k), "y": round(float(v), 2)} for k, v in result.items()]

    if chart_type == "donut":
        result = df.groupby(x)[y].sum() if y else df[x].value_counts()
        result = result[result > 0]
        return [{"label": str(k), "value": round(float(v), 2)} for k, v in result.items()]

    if chart_type == "line":
        dates = pd.to_datetime(df[x], errors="coerce", format="mixed")
        tmp = pd.DataFrame({"d": dates, "v": df[y]}).dropna()
        if tmp.empty:
            return []
        span_days = (tmp["d"].max() - tmp["d"].min()).days
        freq = "M" if span_days > 60 else "D"
        tmp["bucket"] = tmp["d"].dt.to_period(freq).dt.to_timestamp()
        result = tmp.groupby("bucket")["v"].agg(agg).sort_index()
        fmt = "%Y-%m" if freq == "M" else "%Y-%m-%d"
        return [{"x": k.strftime(fmt), "y": round(float(v), 2)} for k, v in result.items()]

    if chart_type == "histogram":
        values = df[x].dropna()
        if values.empty:
            return []
        bins = int(min(20, max(5, round(len(values) ** 0.5))))
        counts, edges = np.histogram(values, bins=bins)
        number_format = "{:.1f}" if (edges[-1] - edges[0]) < 20 else "{:.0f}"
        return [
            {
                "bin": f"{number_format.format(edges[i])} – {number_format.format(edges[i + 1])}",
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ]

    raise ValueError(f"Unknown chart type: {chart_type}")