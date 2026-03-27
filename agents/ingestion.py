import os
from openai import OpenAI
import whisper
from pathlib import Path


def transcribe_audio(file_path: str) -> str:
    """Transcribe audio file to text using Whisper."""
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result["text"]


def ingest(client, raw_input: str, source_type: str = "transcript") -> str:
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

    prompt = f"""{system_prompt}

Source type: {source_type}

Raw input:

{raw_input}"""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
