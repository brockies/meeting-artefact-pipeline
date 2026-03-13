import anthropic


def generate_diagram(client: anthropic.Anthropic, clean_text: str) -> str:
    """
    Diagram Agent — identifies system components and produces a Mermaid diagram.
    """
    system_prompt = """You are the Diagram Agent in a meeting-to-artefact pipeline.

Your job is to identify technical components mentioned in a meeting and produce a Mermaid architecture diagram.

Rules:
- Identify systems, services, platforms, APIs, data stores, and integrations mentioned
- Identify relationships and data flows between them
- Produce a valid Mermaid flowchart (use flowchart LR)
- Label relationships where direction or purpose is clear
- Keep it simple — clarity over completeness
- If there is insufficient technical content for a meaningful diagram, output:
  > No architectural components identified in this meeting.

Output format:

## Architecture Diagram

```mermaid
flowchart LR
    ...
```

## Component Notes
Brief plain-English explanation of what was identified and why.
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
