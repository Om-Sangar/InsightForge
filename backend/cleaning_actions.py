import pandas as pd

def apply_action(df: pd.DataFrame, action: str, column: str = None) -> pd.DataFrame:
    if action == "fill_median":
        df[column] = df[column].fillna(df[column].median())

    elif action == "fill_mode":
        mode_value = df[column].mode()[0]
        df[column] = df[column].fillna(mode_value)

    elif action == "drop_duplicates":
        df = df.drop_duplicates()

    else:
        raise ValueError(f"Unknown action: {action}")

    return df
