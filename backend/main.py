from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import math
import io
import re

from backend.data_profiler import profile_dataframe
from backend.suggestions import generate_suggestions
from backend.cleaning_actions import apply_action
from backend.ai_assistant import generate_ai_suggestions, generate_chat_reply
from backend.table_builder import generate_table_suggestions, build_table

app = FastAPI()

current_data = {"df": None, "original_df": None, "log": []}

PLACEHOLDER_VALUES = [
    "N/A", "NA", "n/a", "null", "NULL", "None", "none",
    "-", "--", "?", "unknown", "Unknown", "UNKNOWN"
]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Suggestion(BaseModel):
    column: str | None = None
    issue: str | None = None
    message: str | None = None
    action: str
    severity: str | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class TableRequest(BaseModel):
    groupby: str
    agg_column: str | None = None
    agg_function: str = "mean"
    title: str | None = None


class CorrectionRequest(BaseModel):
    column: str
    kind: str
    changes: list[dict]  # each: {"row_id": int, "value": str}


def clean_for_json(records: list[dict]) -> list[dict]:
    cleaned = []
    for row in records:
        clean_row = {}
        for key, value in row.items():
            if isinstance(value, float) and math.isnan(value):
                clean_row[key] = None
            elif pd.isna(value):
                clean_row[key] = None
            else:
                clean_row[key] = value
        cleaned.append(clean_row)
    return cleaned


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents), na_values=PLACEHOLDER_VALUES, keep_default_na=True)
    df.columns = df.columns.str.strip()

    current_data["original_df"] = df.copy()
    current_data["df"] = df.copy()
    current_data["log"] = []

    profile = profile_dataframe(df)
    suggestions = generate_suggestions(profile)

    return {
        "filename": file.filename,
        "profile": profile,
        "suggestions": suggestions
    }


@app.post("/apply")
async def apply_cleaning(action: str, column: str = None):
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet. Upload a file first."}

    df = apply_action(df, action, column)
    current_data["df"] = df

    current_data["log"].append({
        "action": action,
        "column": column,
        "message": f"Applied '{action}' on column '{column}'",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    new_profile = profile_dataframe(df)
    new_suggestions = generate_suggestions(new_profile)

    return {
        "message": f"Applied '{action}' on column '{column}'",
        "profile": new_profile,
        "suggestions": new_suggestions,
        "cleaning_log": current_data["log"]
    }


@app.post("/apply-suggestion")
async def apply_suggestion(suggestion: Suggestion):
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet. Upload a file first."}

    df = apply_action(df, suggestion.action, suggestion.column)
    current_data["df"] = df

    current_data["log"].append({
        "action": suggestion.action,
        "column": suggestion.column,
        "message": suggestion.message or f"Applied '{suggestion.action}' on column '{suggestion.column}'",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    new_profile = profile_dataframe(df)
    new_rule_suggestions = generate_suggestions(new_profile)

    return {
        "message": f"Applied '{suggestion.action}' on column '{suggestion.column}'",
        "profile": new_profile,
        "remaining_suggestions": new_rule_suggestions,
        "cleaning_log": current_data["log"]
    }


@app.post("/ai-suggest")
async def ai_suggest():
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet. Upload a file first."}

    profile = profile_dataframe(df)
    ai_suggestions = generate_ai_suggestions(profile)

    return {
        "profile": profile,
        "ai_suggestions": ai_suggestions
    }


@app.get("/cleaning-log")
async def get_cleaning_log():
    return {"cleaning_log": current_data["log"]}


@app.get("/download")
async def download_data():
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet."}

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=cleaned_data.csv"
    return response


@app.post("/chat")
async def chat_with_assistant(req: ChatRequest):
    df = current_data["df"]
    profile = profile_dataframe(df) if df is not None else None
    reply = generate_chat_reply(req.message, req.history, profile)
    return {"reply": reply}


@app.get("/flagged-values")
async def get_flagged_values(column: str, kind: str):
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet."}

    if kind == "outliers":
        q1 = df[column].quantile(0.25)
        q3 = df[column].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        flagged = df[(df[column] < lower) | (df[column] > upper)]

    elif kind == "future_dates":
        parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
        flagged = df[parsed > pd.Timestamp.now()]

    elif kind == "invalid_emails":
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        non_null_mask = df[column].notna()
        invalid_mask = non_null_mask & ~df[column].astype(str).str.match(pattern)
        flagged = df[invalid_mask]

    else:
        return {"error": f"Unknown kind: {kind}"}

    # Include each row's original index so corrections can be mapped back to it
    flagged = flagged.copy()
    flagged.insert(0, "_row_id", flagged.index)

    records = clean_for_json(flagged.to_dict(orient="records"))
    return {"flagged_rows": records}


@app.post("/update-values")
async def update_values(req: CorrectionRequest):
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet."}
    if req.column not in df.columns:
        return {"error": f"Unknown column: {req.column}"}
    if req.kind not in ("invalid_emails", "future_dates"):
        return {"error": f"Unknown kind: {req.kind}"}

    updated = 0
    rejected = []

    for change in req.changes:
        row_id = change.get("row_id")
        value = str(change.get("value", "")).strip()

        if row_id not in df.index:
            rejected.append({"row_id": row_id, "value": value, "reason": "that row no longer exists"})
            continue

        if req.kind == "invalid_emails":
            if not EMAIL_PATTERN.match(value):
                rejected.append({"row_id": row_id, "value": value, "reason": "still not a valid email"})
                continue
            new_value = value

        else:  # future_dates
            parsed = pd.to_datetime(pd.Series([value]), errors="coerce", format="mixed").iloc[0]
            if pd.isna(parsed):
                rejected.append({"row_id": row_id, "value": value, "reason": "not a valid date"})
                continue
            if parsed > pd.Timestamp.now():
                rejected.append({"row_id": row_id, "value": value, "reason": "date is still in the future"})
                continue
            if pd.api.types.is_datetime64_any_dtype(df[req.column]):
                new_value = parsed
            else:
                new_value = parsed.strftime("%Y-%m-%d")

        df.loc[row_id, req.column] = new_value
        updated += 1

    if updated:
        current_data["log"].append({
            "action": "manual_correction",
            "column": req.column,
            "message": f"Manually corrected {updated} value(s) in '{req.column}'",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })

    profile = profile_dataframe(df)
    return {
        "updated": updated,
        "rejected": rejected,
        "profile": profile,
        "remaining_suggestions": generate_suggestions(profile),
        "cleaning_log": current_data["log"]
    }


@app.post("/reset")
async def reset_to_original():
    if current_data["original_df"] is None:
        return {"error": "No original dataset to reset to."}

    df = current_data["original_df"].copy()
    current_data["df"] = df

    current_data["log"].append({
        "action": "reset_to_original",
        "column": None,
        "message": "Reset dataset to its original, unmodified state.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    profile = profile_dataframe(df)
    suggestions = generate_suggestions(profile)

    return {
        "message": "Dataset reset to original.",
        "profile": profile,
        "suggestions": suggestions,
        "cleaning_log": current_data["log"]
    }


@app.get("/compare")
async def compare_original_vs_current():
    original_df = current_data["original_df"]
    current_df = current_data["df"]
    if original_df is None or current_df is None:
        return {"error": "No dataset uploaded yet."}

    return {
        "original": profile_dataframe(original_df),
        "current": profile_dataframe(current_df)
    }


@app.get("/table-suggestions")
async def table_suggestions():
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet."}

    suggestions = generate_table_suggestions(df)
    return {"table_suggestions": suggestions}


@app.post("/create-table")
async def create_table(req: TableRequest):
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet."}

    try:
        rows = build_table(df, req.groupby, req.agg_column, req.agg_function)
        rows = clean_for_json(rows)
    except Exception as e:
        return {"error": str(e)}

    return {"title": req.title or "Summary Table", "rows": rows}