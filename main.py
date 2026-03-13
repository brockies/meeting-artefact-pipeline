import typer
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from pipeline import build_pipeline

load_dotenv()
app = typer.Typer()
console = Console()


@app.command()
def run(
    input_file: Path = typer.Argument(..., help="Path to transcript (.txt), notes (.md), or audio file (.mp3/.wav/.m4a)"),
    output_dir: Path = typer.Option(Path("outputs"), help="Directory to write artefacts to"),
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

    console.print(Panel(
        f"[bold blue]Meeting-to-Artefact Pipeline[/bold blue]\n"
        f"Input: {input_file.name} ({source_type})\n"
        f"Output: {output_dir}/",
        expand=False
    ))

    pipeline = build_pipeline()

    pipeline.invoke({
        "raw_input": raw_input,
        "source_type": source_type,
        "clean_text": "",
        "actions_and_questions": "",
        "diagram": "",
        "output_path": str(output_dir),
    })

    console.print("\n[green]Done.[/green]")


if __name__ == "__main__":
    app()
