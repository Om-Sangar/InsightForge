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
