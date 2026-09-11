import pandas as pd

def apply_action(df: pd.DataFrame, action: str, column: str = None) -> pd.DataFrame:
    if action == "fill_median":
        df[column] = df[column].fillna(df[column].median())

    elif action == "fill_mode":
        mode_value = df[column].mode()[0]
        df[column] = df[column].fillna(mode_value)

    elif action == "drop_duplicates":
        df = df.drop_duplicates()

    elif action == "cap_outliers":
        q1 = df[column].quantile(0.25)
        q3 = df[column].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        df[column] = df[column].clip(lower=lower_bound, upper=upper_bound)

    elif action == "review_outliers":
        pass  # informational only — no data change

    elif action == "standardize_text":
        mask = df[column].notna()
        df.loc[mask, column] = df.loc[mask, column].astype(str).str.strip().str.title()

    else:
        raise ValueError(f"Unknown action: {action}")

    return df