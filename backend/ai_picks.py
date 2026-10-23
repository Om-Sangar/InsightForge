import json

from fastapi import APIRouter
from google.genai import types

from backend.ai_assistant import client
from backend.data_profiler import profile_dataframe
from backend.table_builder import generate_table_suggestions
from backend.chart_builder import generate_chart_suggestions

PICK_LIMIT = 3


def _table_id(t: dict) -> str:
    return f"table|{t['groupby']}|{t.get('agg_column')}|{t['agg_function']}"


def generate_ai_picks(kind: str, candidates: list, profile: dict, limit: int):
    """Returns (picks, error). picks is [{"index", "reason"}] or None; error says why it failed."""
    columns = {
        name: {"type": stats["dtype"], "unique_values": stats["unique_values"]}
        for name, stats in profile["columns"].items()
    }
    numbered = "\n".join(f"{i}. {c['title']}" for i, c in enumerate(candidates, start=1))
    noun = "summary tables" if kind == "tables" else "dashboard charts"

    prompt = f"""You are a data analyst helping a non-technical business user.

Dataset: {profile['row_count']} rows. Columns:
{json.dumps(columns, indent=2)}

Candidate {noun} (numbered):
{numbered}

Choose the {limit} most useful {noun} for understanding this data. Prefer variety (no near-duplicates)
and insights a business owner could act on.

Return ONLY a JSON array in this exact format:
[{{"choice": <number from the list above>, "reason": "one plain-language sentence on why it is useful"}}]
Use only numbers from the list above."""

    raw = ""
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
        raw = (response.text or "").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
    except Exception as e:
        message = f"{type(e).__name__}: {e}"
        print(f"[ai-picks:{kind}] {message}")
        return None, message[:300]

    picks, seen = [], set()
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            choice = int(item.get("choice"))
        except (TypeError, ValueError):
            continue
        if 1 <= choice <= len(candidates) and choice not in seen:
            reason = str(item.get("reason", "")).strip() or "Recommended by the Forge Assistant."
            picks.append({"index": choice - 1, "reason": reason})
            seen.add(choice)

    if not picks:
        message = f"Gemini replied, but no valid choices were found. Raw reply: {raw[:200]}"
        print(f"[ai-picks:{kind}] {message}")
        return None, message

    return picks[:limit], None


def create_ai_picks_router(get_df):
    router = APIRouter()

    @router.get("/ai-picks")
    def ai_picks(kind: str):
        df = get_df()
        if df is None:
            return {"error": "No dataset uploaded yet."}

        if kind == "tables":
            candidates = [{**t, "id": _table_id(t)} for t in generate_table_suggestions(df)]
        elif kind == "charts":
            candidates = generate_chart_suggestions(df)
        else:
            return {"error": f"Unknown kind: {kind}"}

        if not candidates:
            return {"picks": [], "ai": True}

        picks, ai_error = generate_ai_picks(kind, candidates, profile_dataframe(df), PICK_LIMIT)

        if picks is None:  # AI failed or returned nothing usable: fall back to the rule order
            fallback = [
                {**c, "reason": "Suggested by the rule engine (AI is unavailable right now)."}
                for c in candidates[:PICK_LIMIT]
            ]
            return {"picks": fallback, "ai": False, "ai_error": ai_error}

        return {"picks": [{**candidates[p["index"]], "reason": p["reason"]} for p in picks], "ai": True}

    return router