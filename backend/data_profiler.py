import pandas as pd

def profile_dataframe(df: pd.DataFrame) -> dict:
    profile = {}

    for col in df.columns:
        profile[col] = {
            "dtype": str(df[col].dtype),
            "missing_count": int(df[col].isnull().sum()),
            "missing_pct": round(df[col].isnull().mean() * 100, 2),
            "unique_values": int(df[col].nunique()),
        }

    summary = {
        "row_count": df.shape[0],
        "column_count": df.shape[1],
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": profile,
    }

    return summary