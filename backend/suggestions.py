def generate_suggestions(profile: dict) -> list:
    suggestions = []

    for col_name, stats in profile["columns"].items():
        # Missing values
        if stats["missing_pct"] > 0:
            if stats["dtype"] in ("float64", "int64"):
                action = "fill_median"
                message = f"'{col_name}' has {stats['missing_pct']}% missing values — fill with median?"
            else:
                action = "fill_mode"
                message = f"'{col_name}' has {stats['missing_pct']}% missing values — fill with most common value?"

            suggestions.append({
                "column": col_name,
                "issue": "missing_values",
                "message": message,
                "action": action,
                "severity": "high" if stats["missing_pct"] > 30 else "medium"
            })

        # Outliers — flagged for review, never auto-fixed
        if stats.get("outlier_count", 0) > 0:
            suggestions.append({
                "column": col_name,
                "issue": "outliers",
                "message": (
                    f"'{col_name}' has {stats['outlier_count']} value(s) far outside the typical range "
                    f"({stats['lower_bound']}–{stats['upper_bound']}). These may be genuine (e.g. a large "
                    f"real purchase) or data entry errors — review the values before deciding."
                ),
                "action": "review_outliers",
                "severity": "low",
                "outlier_bounds": [stats["lower_bound"], stats["upper_bound"]]
            })

        # Inconsistent text categories (e.g. "Pune" / " pune" / "PUNE")
        if stats.get("inconsistent_variants", 0) > 0:
            example_text = ""
            if stats.get("variant_examples"):
                sample = stats["variant_examples"][0]
                example_text = f" — e.g. {sample} likely mean the same thing"

            suggestions.append({
                "column": col_name,
                "issue": "inconsistent_categories",
                "message": (
                    f"'{col_name}' has {stats['inconsistent_variants']} inconsistently formatted "
                    f"value(s){example_text}. Standardize spacing and capitalization?"
                ),
                "action": "standardize_text",
                "severity": "medium"
            })

    # Duplicate rows (dataset-level, not column-level)
    if profile["duplicate_rows"] > 0:
        suggestions.append({
            "column": None,
            "issue": "duplicate_rows",
            "message": f"Found {profile['duplicate_rows']} fully duplicate rows — remove them?",
            "action": "drop_duplicates",
            "severity": "medium"
        })

    return suggestions