import json
import re
from typing import TypedDict
from langgraph.graph import StateGraph, END

from agents.ingestion import ingest, transcribe_audio
from agents.analyst import analyse
from agents.diagram import generate_diagram
from agents.redaction import tokenize_sensitive_text


class PipelineState(TypedDict):
    raw_input: str
    source_type: str        # 'transcript' | 'notes' | 'audio'
    redaction_mode: str
    custom_redactions: list[str]
    redaction_summary: dict
    clean_text: str
    actions_and_questions: str
    diagram: str
    output_path: str


def ingestion_node(state: PipelineState) -> PipelineState:
    raw = state["raw_input"]
    redaction_summary = {"mode": state.get("redaction_mode", "off"), "counts": {}, "custom_term_count": 0}

    # If audio, transcribe first
    if state["source_type"] == "audio":
        print("  [Ingestion] Transcribing audio...")
        raw = transcribe_audio(raw)  # raw_input is file path for audio

    if state.get("redaction_mode") == "tokenize":
        print("  [Redaction] Tokenising sensitive text...")
        raw, redaction_summary = tokenize_sensitive_text(raw, state.get("custom_redactions", []))

    print("  [Ingestion] Normalising input...")
    clean = ingest(raw, state["source_type"])
    return {**state, "clean_text": clean, "redaction_summary": redaction_summary}


def analyst_node(state: PipelineState) -> PipelineState:
    print("  [Analyst] Extracting actions and questions...")
    result = analyse(state["clean_text"])
    return {**state, "actions_and_questions": result}


def diagram_node(state: PipelineState) -> PipelineState:
    print("  [Diagram] Generating architecture diagram...")
    result = generate_diagram(state["clean_text"])
    return {**state, "diagram": result}


def output_node(state: PipelineState) -> PipelineState:
    from pathlib import Path
    from datetime import datetime

    output_dir = Path(state["output_path"])
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Write actions and questions
    actions_file = output_dir / f"actions_{timestamp}.md"
    actions_file.write_text(state["actions_and_questions"], encoding="utf-8")

    # Write diagram
    diagram_file = output_dir / f"diagram_{timestamp}.mmd"
    mermaid_match = re.search(r'```mermaid\n(.*?)```', state["diagram"], re.DOTALL)
    mermaid_content = mermaid_match.group(1) if mermaid_match else state["diagram"]
    diagram_file.write_text(mermaid_content, encoding="utf-8")

    # Write clean transcript for reference
    clean_file = output_dir / f"clean_transcript_{timestamp}.md"
    clean_file.write_text(f"# Clean Transcript\n\n{state['clean_text']}", encoding="utf-8")

    if state.get("redaction_summary", {}).get("mode") == "tokenize":
        redaction_file = output_dir / f"redaction_{timestamp}.json"
        redaction_file.write_text(
            json.dumps(state["redaction_summary"], indent=2),
            encoding="utf-8",
        )

    print(f"\n  [Output] Artefacts written to {output_dir}")
    print(f"    - {actions_file.name}")
    print(f"    - {diagram_file.name}")
    print(f"    - {clean_file.name}")
    if state.get("redaction_summary", {}).get("mode") == "tokenize":
        print(f"    - {redaction_file.name}")

    return state


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("ingestion", ingestion_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("diagram", diagram_node)
    graph.add_node("output", output_node)

    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "analyst")
    graph.add_edge("analyst", "diagram")
    graph.add_edge("diagram", "output")
    graph.add_edge("output", END)

    return graph.compile()
