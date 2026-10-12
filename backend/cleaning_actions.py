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
        pass

    elif action == "standardize_text":
        mask = df[column].notna()
        df.loc[mask, column] = df.loc[mask, column].astype(str).str.strip().str.title()

    elif action == "parse_dates":
        df[column] = pd.to_datetime(df[column], errors="coerce", format="mixed")

    elif action == "review_future_dates":
        pass  # kept for the flag itself; use the actions below to actually fix

    elif action == "review_invalid_emails":
        pass  # kept for the flag itself; use the actions below to actually fix

    elif action == "blank_invalid_emails":
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        non_null_mask = df[column].notna()
        invalid_mask = non_null_mask & ~df[column].astype(str).str.match(pattern)
        df.loc[invalid_mask, column] = None

    elif action == "drop_invalid_emails":
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        non_null_mask = df[column].notna()
        invalid_mask = non_null_mask & ~df[column].astype(str).str.match(pattern)
        df = df[~invalid_mask]

    elif action == "blank_future_dates":
        parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
        future_mask = parsed > pd.Timestamp.now()
        df.loc[future_mask, column] = None

    elif action == "drop_future_dates":
        parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
        future_mask = parsed > pd.Timestamp.now()
        df = df[~future_mask]

    else:
        raise ValueError(f"Unknown action: {action}")

    return df