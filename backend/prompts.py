from __future__ import annotations

import json


BELIEF_EXTRACTION_SYSTEM = """You are a belief extraction system for a personal knowledge engine.
You analyze a person's recent computer activity (text they read, code they wrote, documents they opened) and extract structured beliefs about them.

RULES:
- Return ONLY valid JSON. No explanation, no preamble, no markdown.
- Be conservative with confidence scores. Default to 0.5 unless evidence is strong.
- Only extract beliefs that are clearly supported by the captures.
- Do not invent or infer beyond what the data shows.
- Keep all strings concise — under 100 characters each.
- belief_type must be exactly one of: interest, knowledge, gap, pattern, project"""


def build_extraction_prompt(captures: list[dict], existing_beliefs: list[dict]) -> str:
    captures_text = "\n---\n".join(
        [
            f"ID: {c['id']}\nApp: {c['app_name']}\nWindow: {c.get('window_title', '')}\nContent: {c['content'][:400]}"
            for c in captures[:40]
        ]
    )
    existing_text = json.dumps(existing_beliefs[:20], indent=2) if existing_beliefs else "[]"

    return f"""Analyze these recent computer activity captures and extract or update beliefs about the user.

RECENT CAPTURES (last 6 hours):
{captures_text}

EXISTING BELIEFS (for context — update confidence if reinforced, do not duplicate):
{existing_text}

Return a JSON object with this exact structure:
{{
  "new_beliefs": [
    {{
      "topic": "string — the subject (e.g. FAISS vector indexing)",
      "belief_type": "interest|knowledge|gap|pattern|project",
      "summary": "string — one sentence describing the belief",
      "confidence": 0.0-1.0,
      "depth": "surface|familiar|intermediate|deep",
      "evidence_summary": "string — what in the captures supports this"
    }}
  ],
  "reinforced_topics": [
    "topic string that already exists in beliefs and was seen again"
  ],
  "gaps_detected": [
    "topic the user keeps searching but shows no deep engagement with"
  ]
}}"""


USER_MODEL_SYSTEM = """You are summarizing a person's user model for display in a personal dashboard.
Return ONLY valid JSON. Be concise and honest. Do not flatter."""


def build_user_model_prompt(beliefs: list[dict]) -> str:
    beliefs_text = json.dumps(beliefs, indent=2)

    return f"""Given these structured beliefs about a user, generate a user model summary.

BELIEFS:
{beliefs_text}

Return a JSON object with this exact structure:
{{
  "summary": "2-3 sentence plain English description of who this person is based on their computer activity",
  "top_interests": ["interest1", "interest2", "interest3", "interest4", "interest5"],
  "active_projects": ["project or focus area currently active"],
  "work_rhythm": "one sentence describing when and how they work",
  "knowledge_gaps": ["topic they engage with superficially but haven't internalized"]
}}"""
