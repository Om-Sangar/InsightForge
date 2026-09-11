from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import math
import io

from backend.data_profiler import profile_dataframe
from backend.suggestions import generate_suggestions
from backend.cleaning_actions import apply_action
from backend.ai_assistant import generate_ai_suggestions, generate_chat_reply

app = FastAPI()

current_data = {"df": None, "log": []}


class Suggestion(BaseModel):
    column: str | None = None
    issue: str | None = None
    message: str | None = None
    action: str
    severity: str | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


def clean_for_json(records: list[dict]) -> list[dict]:
    """Replace any NaN/NaT values with None so the response is valid JSON."""
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
    df = pd.read_csv(io.BytesIO(contents))
    df.columns = df.columns.str.strip()

    current_data["df"] = df
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


@app.get("/outlier-values")
async def get_outlier_values(column: str):
    df = current_data["df"]
    if df is None:
        return {"error": "No dataset uploaded yet."}

    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    outliers = df[(df[column] < lower) | (df[column] > upper)]
    records = outliers.to_dict(orient="records")
    records = clean_for_json(records)

    return {"outlier_rows": records}