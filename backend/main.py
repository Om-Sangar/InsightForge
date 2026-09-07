from fastapi import FastAPI, UploadFile, File
import pandas as pd
import io
from backend.data_profiler import profile_dataframe
from backend.suggestions import generate_suggestions
from backend.cleaning_actions import apply_action

app = FastAPI()

# Temporary in-memory storage — holds the "current" dataset between requests
current_data = {"df": None}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))
    df.columns = df.columns.str.strip()

    current_data["df"] = df  # save it so /apply can use it later

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
    current_data["df"] = df  # save the updated version

    new_profile = profile_dataframe(df)
    new_suggestions = generate_suggestions(new_profile)

    return {
        "message": f"Applied '{action}' on column '{column}'",
        "profile": new_profile,
        "suggestions": new_suggestions
    }
