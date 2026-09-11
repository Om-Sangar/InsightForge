import pandas as pd

def profile_dataframe(df: pd.DataFrame) -> dict:
    profile = {}

    for col in df.columns:
        col_stats = {
            "dtype": str(df[col].dtype),
            "missing_count": int(df[col].isnull().sum()),
            "missing_pct": round(df[col].isnull().mean() * 100, 2),
            "unique_values": int(df[col].nunique()),
        }

        if pd.api.types.is_numeric_dtype(df[col]):
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            outlier_count = int(((df[col] < lower_bound) | (df[col] > upper_bound)).sum())

            col_stats["outlier_count"] = outlier_count
            col_stats["outlier_pct"] = round((outlier_count / len(df)) * 100, 2) if len(df) > 0 else 0
            col_stats["lower_bound"] = round(float(lower_bound), 2) if pd.notna(lower_bound) else None
            col_stats["upper_bound"] = round(float(upper_bound), 2) if pd.notna(upper_bound) else None

        else:
            non_null = df[col].dropna().astype(str)
            if len(non_null) > 0:
                normalized = non_null.str.strip().str.lower()
                raw_unique = non_null.nunique()
                normalized_unique = normalized.nunique()
                inconsistent_count = raw_unique - normalized_unique

                col_stats["inconsistent_variants"] = int(inconsistent_count)

                if inconsistent_count > 0:
                    temp = pd.DataFrame({"raw": non_null.values, "norm": normalized.values})
                    grouped = temp.groupby("norm")["raw"].unique()
                    examples = [list(v) for v in grouped if len(v) > 1]
                    col_stats["variant_examples"] = examples[:3]

        profile[col] = col_stats

    summary = {
        "row_count": df.shape[0],
        "column_count": df.shape[1],
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": profile,
    }

    return summary