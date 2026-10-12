import pandas as pd

IDENTIFIER_TOKENS = {"id", "email", "phone"}
SUM_TOKENS = {"amount", "price", "revenue", "sales", "total", "cost", "spend"}


def _tokens(col: str) -> set:
    return set(col.lower().replace("-", "_").replace(" ", "_").split("_"))


def classify_columns(df: pd.DataFrame) -> dict:
    categorical = []
    numeric = []
    identifier = []

    row_count = len(df)

    for col in df.columns:
        tokens = _tokens(col)
        nunique = df[col].nunique()
        uniqueness_ratio = nunique / row_count if row_count > 0 else 0
        is_float = pd.api.types.is_float_dtype(df[col])

        if tokens & IDENTIFIER_TOKENS:
            identifier.append(col)
        elif "name" in tokens and uniqueness_ratio > 0.5:
            identifier.append(col)
        elif uniqueness_ratio > 0.9 and not is_float:
            # Near-unique integers/text are identifiers. Decimal columns
            # (like purchase_amount) are naturally near-unique and are NOT.
            identifier.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric.append(col)
        elif 1 < nunique < row_count * 0.3:
            categorical.append(col)

    # Put sum-type columns (amount, revenue, ...) first so business totals lead
    numeric.sort(key=lambda c: 0 if _tokens(c) & SUM_TOKENS else 1)

    return {
        "categorical": categorical,
        "numeric": numeric,
        "identifier": identifier
    }


def generate_table_suggestions(df: pd.DataFrame) -> list:
    classification = classify_columns(df)
    suggestions = []

    for cat_col in classification["categorical"]:
        suggestions.append({
            "title": f"Count by {cat_col}",
            "groupby": cat_col,
            "agg_column": None,
            "agg_function": "count",
            "rationale": f"How many records fall into each {cat_col}?"
        })

        for num_col in classification["numeric"]:
            agg_function = "sum" if _tokens(num_col) & SUM_TOKENS else "mean"

            suggestions.append({
                "title": f"{agg_function.title()} of {num_col} by {cat_col}",
                "groupby": cat_col,
                "agg_column": num_col,
                "agg_function": agg_function,
                "rationale": f"{agg_function.title()} {num_col} grouped by {cat_col}"
            })

    return suggestions[:8]


def build_table(df: pd.DataFrame, groupby: str, agg_column: str | None, agg_function: str) -> list:
    if agg_column is None or agg_function == "count":
        result = df.groupby(groupby).size().reset_index(name="count")
    else:
        result = df.groupby(groupby)[agg_column].agg(agg_function).reset_index()
        result[agg_column] = result[agg_column].round(2)

    return result.to_dict(orient="records")