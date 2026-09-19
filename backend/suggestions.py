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

        # Inconsistent text categories
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

        # Date parsing
        if stats.get("likely_date") and stats.get("invalid_date_count", 0) > 0:
            suggestions.append({
                "column": col_name,
                "issue": "unparseable_dates",
                "message": (
                    f"'{col_name}' looks like a date column with {stats['invalid_date_count']} value(s) "
                    f"that aren't valid dates. Convert to proper date format? (unparseable values become missing)"
                ),
                "action": "parse_dates",
                "severity": "medium"
            })

        # Future dates — flagged for review, not auto-fixed
        if stats.get("likely_date") and stats.get("future_date_count", 0) > 0:
            suggestions.append({
                "column": col_name,
                "issue": "future_dates",
                "message": (
                    f"'{col_name}' has {stats['future_date_count']} date(s) in the future. "
                    f"This could be intentional (e.g. a scheduled date) or an entry error — review before deciding."
                ),
                "action": "review_future_dates",
                "severity": "low"
            })

        # Invalid email formats — flagged for review, not auto-fixed
        if stats.get("likely_email") and stats.get("invalid_email_count", 0) > 0:
            suggestions.append({
                "column": col_name,
                "issue": "invalid_emails",
                "message": (
                    f"'{col_name}' has {stats['invalid_email_count']} value(s) that don't look like valid "
                    f"email addresses. Review them before deciding what to do."
                ),
                "action": "review_invalid_emails",
                "severity": "low"
            })

    if profile["duplicate_rows"] > 0:
        suggestions.append({
            "column": None,
            "issue": "duplicate_rows",
            "message": f"Found {profile['duplicate_rows']} fully duplicate rows — remove them?",
            "action": "drop_duplicates",
            "severity": "medium"
        })

    return suggestions