import anthropic


def analyse(client: anthropic.Anthropic, clean_text: str) -> str:
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

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Cleaned transcript:\n\n{clean_text}"
            }
        ]
    )

    return message.content[0].text
