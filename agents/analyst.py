import os
from openai import OpenAI


def analyse(client, clean_text: str) -> str:
    """
    Analyst Agent — extracts actions and open questions from cleaned transcript.
    """
    system_prompt = """You are the Analyst Agent in a meeting-to-artefact pipeline.

Your job is to extract structured actions and open questions from a cleaned meeting transcript.

Rules:
- Identify all action items with owner and deadline if mentioned
- Identify all open questions — things raised but not resolved
- If no owner is identifiable, mark as UNASSIGNED
- Do not resolve questions — surface them exactly as raised
- Never invent actions or questions not present in the text

Output format (strict markdown):

## Actions
- [ ] [OWNER] Action description _(deadline if mentioned)_

## Open Questions
- Q: Question text
"""

    prompt = f"""{system_prompt}

Cleaned transcript:

{clean_text}"""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
