import typer
import os
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from pipeline import build_pipeline
from agents.redaction import parse_sensitive_terms

load_dotenv()
app = typer.Typer()
console = Console()


@app.command()
def run(
    input_file: Path = typer.Argument(..., help="Path to transcript (.txt), notes (.md), or audio file (.mp3/.wav/.m4a)"),
    output_dir: Path = typer.Option(Path("outputs"), help="Directory to write artefacts to"),
    redaction_mode: str = typer.Option("off", help="Redaction mode: off or tokenize"),
    sensitive_term: list[str] | None = typer.Option(None, "--sensitive-term", help="Additional sensitive term to tokenize. Repeat to pass multiple values."),
):
    """
    Meeting-to-Artefact Pipeline
    Drop in a transcript, notes, or voice recording and get back actions and an architecture diagram.
    """
    if not input_file.exists():
        console.print(f"[red]Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    # Detect source type from extension
    audio_extensions = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
    suffix = input_file.suffix.lower()

    if suffix in audio_extensions:
        source_type = "audio"
        raw_input = str(input_file)  # Pass path for Whisper to handle
    else:
        source_type = "transcript" if suffix in {".txt"} else "notes"
        raw_input = input_file.read_text(encoding="utf-8")

    redaction_mode = redaction_mode.lower().strip()
    if redaction_mode not in {"off", "tokenize"}:
        console.print(f"[red]Unsupported redaction mode: {redaction_mode}. Use 'off' or 'tokenize'.[/red]")
        raise typer.Exit(1)

    custom_redactions = list(sensitive_term or [])
    env_redactions = parse_sensitive_terms(os.getenv("REDACTION_TERMS", ""))
    for term in env_redactions:
        if term not in custom_redactions:
            custom_redactions.append(term)

    console.print(Panel(
        f"[bold blue]Meeting-to-Artefact Pipeline[/bold blue]\n"
        f"Input: {input_file.name} ({source_type})\n"
        f"Output: {output_dir}/\n"
        f"Redaction: {redaction_mode}",
        expand=False
    ))

    pipeline = build_pipeline()

    pipeline.invoke({
        "raw_input": raw_input,
        "source_type": source_type,
        "redaction_mode": redaction_mode,
        "custom_redactions": custom_redactions,
        "redaction_summary": {"mode": redaction_mode, "counts": {}, "custom_term_count": len(custom_redactions)},
        "clean_text": "",
        "actions_and_questions": "",
        "diagram": "",
        "output_path": str(output_dir),
    })

    console.print("\n[green]Done.[/green]")


if __name__ == "__main__":
    app()
