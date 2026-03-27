"""
agents/decisions.py — Decision Log Agent
Extracts decisions made during the meeting from the clean transcript.
"""

import os
from openai import OpenAI

DECISIONS_PROMPT = """You are the Decision Log Agent. Your role is to extract decisions that were
made during this meeting — things that were agreed, confirmed, or resolved.

Rules:
- Only extract genuine decisions — things explicitly agreed or confirmed by the group
- Do not include actions (things to be done) or open questions (things unresolved)
- If a decision has a clear rationale mentioned, capture it briefly
- If no real decisions were made, output a note saying so rather than fabricating content
- Always output valid markdown

Output format:

## Decisions

- **[TOPIC]** Decision description. _(Rationale: brief reason if mentioned)_

Example:
- **[AUTH SERVICE]** The new auth microservice will be containerised and deployed independently of the monolith. _(Rationale: reduces deployment coupling)_
- **[DATABASE]** Postgres will be used as the primary data store for the new service.
"""


def extract_decisions(clean_text: str) -> str:
    """
    Extract decisions from the clean transcript.
    Returns a markdown string with a ## Decisions section.
    """
    prompt = f"{DECISIONS_PROMPT}\n\n---\n\n{clean_text}"
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
