from google import genai
import os
import json
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_ai_suggestions(profile: dict) -> list:
    prompt = f"""
You are a data cleaning assistant. Given this dataset profile, suggest cleaning actions.

Profile:
{json.dumps(profile, indent=2)}

Return ONLY a JSON array, no other text, no markdown formatting, in this exact format:
[
  {{
    "column": "column_name",
    "issue": "short issue description",
    "message": "plain language suggestion ending in a question mark",
    "action": "fill_median" or "fill_mode" or "drop_duplicates",
    "severity": "high" or "medium" or "low"
  }}
]

Only use these exact action values: fill_median, fill_mode, drop_duplicates.
If there are no issues, return an empty array: []
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    raw_text = response.text.strip()
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        suggestions = json.loads(raw_text)
    except json.JSONDecodeError:
        suggestions = []

    return suggestions


def generate_chat_reply(message: str, history: list, profile: dict | None) -> str:
    context = ""
    if profile:
        context = f"Current dataset profile:\n{json.dumps(profile, indent=2)}\n\n"

    convo = ""
    for turn in history:
        role = "User" if turn["role"] == "user" else "Assistant"
        convo += f"{role}: {turn['content']}\n"

    prompt = f"""You are the Forge Assistant, a helpful data cleaning and analysis assistant
inside InsightForge. Answer the user's question conversationally and concisely,
using the dataset profile as context when relevant. Keep answers short (2-4 sentences)
unless the user asks for detail. If a cleaning action would help, describe it in plain
language — the user applies actions through the suggestion cards, not through this chat.

{context}Conversation so far:
{convo}User: {message}
Assistant:"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    return response.text.strip()