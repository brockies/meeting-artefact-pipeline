import anthropic
import whisper
from pathlib import Path


def transcribe_audio(file_path: str) -> str:
    """Transcribe audio file to text using Whisper."""
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result["text"]


def ingest(client: anthropic.Anthropic, raw_input: str, source_type: str = "transcript") -> str:
    """
    Ingestion Agent — normalises raw input into clean structured text.
    source_type: 'transcript' | 'notes' | 'audio_text'
    """
    system_prompt = """You are the Ingestion Agent in a meeting-to-artefact pipeline.
    
Your job is to normalise raw meeting input into clean, readable text.

Rules:
- Remove filler words, repetition, and conversational noise
- Preserve all technical terms, system names, and proper nouns exactly as spoken
- Preserve chronological order of topics
- Flag any unclear or ambiguous sections with [UNCLEAR: ...]
- Do not invent or infer information not present in the source
- Output clean prose, not bullet points
"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Source type: {source_type}\n\nRaw input:\n\n{raw_input}"
            }
        ]
    )

    return message.content[0].text
