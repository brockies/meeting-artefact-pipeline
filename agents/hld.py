"""
agents/hld.py — High Level Design Generation Agent
Synthesises all pipeline outputs into a structured HLD document.
"""

import json
import os
import re
from openai import OpenAI

HLD_PROMPT = """You are a Senior Solutions Architect. Your task is to synthesise the outputs
from a meeting analysis pipeline into a structured High Level Design (HLD) document.

You will be given:
- A clean meeting transcript
- Extracted action items and open questions
- A decision log
- A Mermaid architecture diagram (as text)

Your job is to produce a structured HLD in JSON format. Be professional, concise, and grounded
in the source material — do not invent information not present in the inputs.

Return ONLY valid JSON matching this exact structure (no markdown fences, no preamble):

{
  "document_control": {
    "title": "HLD title derived from the meeting content",
    "version": "0.1",
    "status": "Draft",
    "date": "TODAY"
  },
  "executive_summary": "2-3 sentence summary of what this HLD covers and why it matters.",
  "background": "1-2 paragraphs covering the problem or context that led to this design discussion.",
  "current_state": {
    "description": "Description of the current state architecture or situation.",
    "limitations": ["limitation 1", "limitation 2"]
  },
  "proposed_architecture": {
    "description": "Description of the proposed architecture and key design approach.",
    "components": [
      { "name": "Component name", "description": "What it does and its role" }
    ],
    "key_flows": ["Description of key data or process flow 1", "flow 2"]
  },
  "design_decisions": [
    { "decision": "The decision made", "rationale": "Why this decision was made" }
  ],
  "risks_and_open_questions": [
    { "type": "Risk or Open Question", "description": "Description", "owner": "Owner if known or TBC" }
  ],
  "next_steps": [
    { "action": "Action description", "owner": "Owner name or UNASSIGNED" }
  ]
}
"""


def generate_hld_content(client, clean_text: str, actions_and_questions: str,
                          decisions_raw: str, diagram_raw: str) -> dict:
    """
    Call Claude to synthesise all pipeline outputs into structured HLD content.
    Returns a dict ready for docx rendering.
    """
    from datetime import datetime
    today = datetime.now().strftime("%d %B %Y")

    user_content = f"""Please generate an HLD from the following meeting outputs.

## Clean Transcript
{clean_text}

## Actions and Open Questions
{actions_and_questions}

## Decision Log
{decisions_raw}

## Architecture Diagram (Mermaid)
{diagram_raw}

Today's date is {today}. Use this for the document_control.date field.
"""

    prompt = f"{HLD_PROMPT}\n\n{user_content}"
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content.strip()

    # Strip any accidental markdown fences
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    return json.loads(raw)
