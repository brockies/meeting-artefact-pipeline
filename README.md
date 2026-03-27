# Meeting-to-Artefact Pipeline

Drop in a meeting transcript, notes, or voice recording — get back structured actions and an architecture diagram.

## What it produces
- `actions_[timestamp].md` — action items with owners, and open questions
- `diagram_[timestamp].md` — Mermaid architecture diagram of systems discussed
- `clean_transcript_[timestamp].md` — normalised transcript for reference

## Setup

### 1. Clone and install
```bash
git clone <your-repo>
cd meeting-artefact-pipeline
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Add your Claude API key to .env
```
Get your Claude API key at: https://console.anthropic.com

### 3. Run
#### Streamlit app (Windows Git Bash)
```bash
source venv/Scripts/activate
python -m streamlit run app.py
```

#### CLI examples
```bash
# From a transcript (.txt)
python main.py inputs/my_meeting.txt

# From notes (.md)
python main.py inputs/my_notes.md

# From a voice recording
python main.py inputs/recording.m4a

# Specify output directory
python main.py inputs/my_meeting.txt --output-dir outputs/project-x
```

## Project Structure
```
meeting-artefact-pipeline/
├── AGENTS.md              # Agent behaviour definitions
├── main.py                # CLI entry point
├── pipeline.py            # LangGraph orchestration
├── agents/
│   ├── ingestion.py       # Normalises raw input
│   ├── analyst.py         # Extracts actions and questions
│   └── diagram.py         # Generates Mermaid diagram
├── inputs/                # Drop your meeting files here
├── outputs/               # Artefacts written here
├── requirements.txt
└── .env.example
```

## Stack
- **LLM:** Claude (Anthropic) — long context, great structured output
- **Orchestration:** LangGraph
- **Voice transcription:** Whisper (runs locally, no API cost)
- **Diagrams:** Mermaid (renders in GitHub, Notion, VS Code)

## Azure Deployment (future)
The pipeline is stateless and containerisable. To deploy to Azure:
1. Build as a Docker container
2. Deploy to Azure Container Apps
3. Swap `ANTHROPIC_API_KEY` for Azure OpenAI credentials in `.env`
