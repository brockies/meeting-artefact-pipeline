"""
app.py — Streamlit UI for the Meeting-to-Artefact Pipeline
Drop alongside pipeline.py in the project root and run:
    streamlit run app.py
"""

import re
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Meeting Artefact Pipeline",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

HISTORY_DIR = Path("history")
HISTORY_DIR.mkdir(exist_ok=True)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Base ── */
  html, body, [class*="css"] {
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #1E293B;
  }

  .block-container {
    padding-top: 0.5rem !important;
    padding-left: 2rem !important;
  }
  header[data-testid="stHeader"] { background: transparent; }
  [data-testid="stSidebarCollapseButton"] { display: block !important; }

  /* ── Main background ── */
  .stApp { background: #E2E8F0; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {   
    background: #FFFFFF !important;
    border-right: 1px solid #E2E8F0 !important;
  }
  section[data-testid="stSidebar"] {
    width: 280px !important;
    min-width: 280px !important;
  }
  section[data-testid="stSidebar"] > div:first-child {
    width: 280px !important;
    min-width: 280px !important;
    padding-top: 0.5rem !important;
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
  }
  [data-testid="stSidebar"] hr {
    border-color: #E2E8F0 !important;
    margin: 0.6rem 0 !important;
  }

  /* Sidebar secondary buttons (meeting entries, delete) */
  [data-testid="stSidebar"] .stButton button {
    background: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    color: #475569 !important;
    border-radius: 7px !important;
    font-size: 0.88rem !important;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    transition: all 0.15s ease !important;
    text-align: left !important;
    padding: 0.65rem 1rem !important;
    font-weight: 500 !important;
    min-height: 42px !important;
  }
  [data-testid="stSidebar"] .stButton button[kind="secondary"] {
    font-size: 1.1rem !important;
    padding: 0.4rem 0.6rem !important;
  }
  [data-testid="stSidebar"] .stButton button:hover {
    background: #EFF6FF !important;
    border-color: #6366F1 !important;
    color: #4338CA !important;
  }

  /* Fix sidebar text */
  [data-testid="stSidebar"] {
    color: #1E293B !important;
  }
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] div {
    color: #1E293B !important;
  }
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3 {
    color: #0F172A !important;
    font-weight: 600 !important;
  }

  /* ── Header block ── */
  .header-block {
    padding: 0.4rem 0 1.2rem 0;
    border-bottom: 1px solid #E2E8F0;
    margin-bottom: 1.4rem;
    position: relative;
  }
  .header-block::after {
    content: '';
    position: absolute;
    bottom: -1px; left: 0;
    width: 56px; height: 2px;
    background: linear-gradient(90deg, #6366F1, #38BDF8);
    border-radius: 2px;
  }
  .header-block h1 {
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #0F172A;
    margin: 0;
    line-height: 1.25;
  }
  .header-block p {
    color: #94A3B8;
    margin: 0.35rem 0 0 0;
    font-size: 0.88rem;
    font-weight: 400;
  }

  /* ── Agent progress cards ── */
  .agent-card {
    display: flex; align-items: center; gap: 1rem;
    padding: 1rem 1.4rem; border-radius: 8px; margin-bottom: 0.5rem;
    font-size: 1.05rem; font-weight: 500;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif;
    border: 1px solid transparent;
    transition: all 0.2s ease;
  }
  .agent-card.waiting {
    background: #F8FAFC; color: #94A3B8;
    border-color: #E2E8F0;
  }
  .agent-card.running {
    background: #EFF6FF; color: #3B82F6;
    border-color: #BFDBFE;
    box-shadow: 0 1px 8px rgba(99,102,241,0.08);
  }
  .agent-card.done {
    background: #F0FDF4; color: #16A34A;
    border-color: #BBF7D0;
  }
  .agent-card .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .agent-card.waiting .dot { background: #CBD5E1; }
  .agent-card.running .dot {
    background: #3B82F6;
    animation: pulse-ring 1.2s infinite;
  }
  .agent-card.done .dot { background: #16A34A; }
  .agent-card strong {
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    font-size: 1.05rem;
    font-weight: 700;
  }

  @keyframes pulse-ring {
    0%, 100% { opacity: 1; transform: scale(1); box-shadow: 0 0 0 0 rgba(59,130,246,0.4); }
    50%       { opacity: 0.8; transform: scale(1.3); box-shadow: 0 0 0 4px rgba(59,130,246,0); }
  }

  /* ── Result cards ── */
  .action-item {
    display: flex; align-items: flex-start; gap: 0.75rem;
    padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 3px solid #6366F1;
    font-size: 0.88rem; color: #1E293B;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.15s;
  }
  .action-item:hover { box-shadow: 0 2px 8px rgba(99,102,241,0.1); }

  .action-owner {
    background: #6366F1;
    color: white;
    padding: 0.2rem 0.65rem; border-radius: 4px;
    font-size: 0.72rem; font-family: 'Courier New', Courier, monospace;
    white-space: nowrap; font-weight: 500;
    letter-spacing: 0.3px;
  }
  .action-owner.unassigned { background: #94A3B8; }

  .question-item {
    padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-left: 3px solid #F59E0B;
    font-size: 0.88rem; color: #1E293B;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }

  .decision-item {
    display: flex; align-items: flex-start; gap: 0.75rem;
    padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    border-left: 3px solid #16A34A;
    font-size: 0.88rem; color: #1E293B;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .decision-owner {
    background: #16A34A;
    color: white;
    padding: 0.2rem 0.65rem; border-radius: 4px;
    font-size: 0.72rem; font-family: 'Courier New', Courier, monospace;
    white-space: nowrap; font-weight: 500;
  }
  .decision-owner.team { background: #0891B2; }

  /* ── Sidebar date headers ── */
  .meeting-date-header {
    font-size: 0.68rem; font-weight: 600; letter-spacing: 1.2px;
    text-transform: uppercase; color: #94A3B8;
    margin: 1.1rem 0 0.4rem 0;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
  }

  /* ── Tabs ── */
  [data-testid="stTabs"] {
    border-bottom: 2px solid #E2EF0 !important;
    margin-bottom: 1rem !important;
  }
  [data-testid="stTabs"] button {
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    color: #475569 !important;
    letter-spacing: 0.2px;
  }
  [data-testid="stTabs"] button[aria-selected="true"] {
    color: #4338CA !important;
    font-weight: 700 !important;
  }

  /* ── Metrics ── */
  div[role="tablist"] {
    border-bottom: 2px solid #E2E8F0 !important;
    gap: 0.5rem !important;
  }
  button[role="tab"] {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    color: #475569 !important;
  }
  button[role="tab"][aria-selected="true"] {
    color: #4338CA !important;
    font-weight: 700 !important;
  }
  .stTabs [data-baseweb="tab-list"] {
    border-bottom: 2px solid #E2E8F0 !important;
    gap: 0.5rem !important;
    margin-bottom: 1rem !important;
  }
  .stTabs [data-baseweb="tab"] {
    padding: 0.6rem 1.2rem !important;
  }
  .stTabs [data-baseweb="tab-highlight"] {
    background-color: #4338CA !important;
  }
  .stTabs [data-baseweb="tab"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #475569 !important;
  }
  .stTabs [data-baseweb="tab"][aria-selected="true"] [data-testid="stMarkdownContainer"] p {
    color: #4338CA !important;
    font-weight: 700 !important;
  }

  [data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  [data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    color: #94A3B8 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-family: 'Courier New', Courier, monospace !important;
  }
  [data-testid="stMetricValue"] {
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    line-height: 1.1 !important;
  }

  /* ── File uploader ── */
  [data-testid="stCheckbox"] label,
  [data-testid="stCheckbox"] label p,
  [data-testid="stCheckbox"] span {
    color: #1E293B !important;
  }

  [data-testid="stFileUploader"] {
    background: #FFFFFF !important;
    border: 1.5px dashed #CBD5E1 !important;
    border-radius: 10px !important;
    transition: border-color 0.2s;
  }
  [data-testid="stFileUploader"]:hover {
    border-color: #6366F1 !important;
  }

  /* ── Primary buttons ── */
  .stButton button[kind="primary"] {
    background: linear-gradient(135deg, #6366F1, #4F46E5) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    border-radius: 7px !important;
    letter-spacing: 0.2px;
    box-shadow: 0 2px 8px rgba(99,102,241,0.25);
    transition: all 0.15s;
  }
  .stButton button[kind="primary"]:hover {
    box-shadow: 0 4px 16px rgba(99,102,241,0.35) !important;
    transform: translateY(-1px);
  }

  [data-testid="stSidebar"] .stButton button[kind="primary"],
  [data-testid="stSidebar"] .stButton button[kind="primary"] p,
  [data-testid="stSidebar"] .stButton button[kind="primary"] span,
  [data-testid="stSidebar"] .stButton button[kind="primary"] * {
    color: white !important;
  }

  /* ── Secondary buttons ── */
  .stButton button[kind="secondary"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    color: #475569 !important;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    border-radius: 7px !important;
    transition: all 0.15s;
  }
  .stButton button[kind="secondary"]:hover {
    border-color: #6366F1 !important;
    color: #4338CA !important;
  }

  /* ── Download buttons ── */
  [data-testid="stDownloadButton"] button {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    color: #64748B !important;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    font-size: 0.83rem !important;
    border-radius: 6px !important;
    transition: all 0.15s;
  }
  [data-testid="stDownloadButton"] button:hover {
    border-color: #6366F1 !important;
    color: #4338CA !important;
  }

  /* ── Inputs ── */
  [data-testid="stTextInput"] input {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 7px !important;
    color: #1E293B !important;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
  }
  [data-testid="stTextInput"] input:focus {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important;
  }

  /* ── Checkboxes ── */
  [data-testid="stCheckbox"] label {
    color: #475569 !important;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    font-size: 0.88rem !important;
  }

  /* ── Code blocks ── */
  [data-testid="stCode"] {
    background: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
  }

  /* ── Divider ── */
  hr {
    border: none !important;
    border-top: 1px solid #E2E8F0 !important;
    margin: 1.2rem 0 !important;
  }

  /* ── Chat interface ── */
  .chat-message {
    display: flex; gap: 0.75rem; margin-bottom: 1rem;
    align-items: flex-start;
  }
  .chat-message.user { flex-direction: row-reverse; }

  .chat-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85rem; flex-shrink: 0; font-weight: 600;
  }
  .chat-avatar.user {
    background: linear-gradient(135deg, #6366F1, #4F46E5);
    color: white;
  }
  .chat-avatar.assistant {
    background: #F1F5F9;
    border: 1px solid #E2E8F0;
    color: #475569;
  }

  .chat-bubble {
    max-width: 80%; padding: 0.85rem 1.1rem;
    border-radius: 12px; font-size: 0.9rem;
    line-height: 1.6; color: #1E293B;
  }
  .chat-bubble.user {
    background: linear-gradient(135deg, #6366F1, #4F46E5);
    color: white;
    border-bottom-right-radius: 4px;
  }
  .chat-bubble.assistant {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-bottom-left-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .chat-bubble.assistant strong { font-weight: 700; color: #0F172A; }
  .chat-bubble.assistant h1,
  .chat-bubble.assistant h2,
  .chat-bubble.assistant h3 {
    font-size: 1rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin: 0.5rem 0 0.25rem 0 !important;
  }
  .chat-bubble.assistant ul,
  .chat-bubble.assistant li {
    margin-left: 1rem !important;
    color: #1E293B !important;
  }

  .chat-empty {
    text-align: center; padding: 3rem 2rem;
    color: #94A3B8;
  }
  .chat-empty .icon { font-size: 2.5rem; margin-bottom: 0.75rem; opacity: 0.4; }
  .chat-empty .title {
    font-family: Georgia, 'Times New Roman', serif; font-size: 1.1rem;
    font-weight: 600; color: #475569; margin-bottom: 0.5rem;
  }
  .chat-empty .subtitle { font-size: 0.85rem; color: #94A3B8; }

  .chat-suggestions {
    display: flex; flex-wrap: wrap; gap: 0.5rem;
    margin-top: 1.5rem; justify-content: center;
  }
  .chat-suggestion {
    background: #FFFFFF; border: 1px solid #E2E8F0;
    border-radius: 20px; padding: 0.4rem 1rem;
    font-size: 0.82rem; color: #475569; cursor: pointer;
    transition: all 0.15s;
  }
  .chat-suggestion:hover {
    border-color: #6366F1; color: #4338CA;
    background: #EFF6FF;
  }

  /* ── File uploader ── */
  [data-testid="stFileUploaderDropzone"] {
    background: #FFFFFF !important;
  }
  [data-testid="stFileUploaderDropzone"] * {
    color: #475569 !important;
  }
  [data-testid="stFileUploaderDropzone"] button {
    background: #F1F5F9 !important;
    border: 1px solid #E2E8F0 !important;
    color: #475569 !important;
    border-radius: 6px !important;
  }
  

  /* Fix uploaded filename visibility */
  [data-testid="stFileUploaderFile"] {
    color: #1E293B !important;
  }
  [data-testid="stFileUploaderFile"] * {
    color: #1E293B !important;
  }
  [data-testid="stFileUploaderFile"] small {
    color: #94A3B8 !important;
  }

  /* Fix right column info text */
  .stMarkdown h4, .stMarkdown h3, .stMarkdown h2, .stMarkdown h1 {
    color: #0F172A !important;
    font-family: -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
  }
  .stMarkdown p, .stMarkdown li {
    color: #475569 !important;
  }
  .stMarkdown strong {
    color: #0F172A !important;
  }
  .stMarkdown code {
    background: #EEF2FF !important;
    color: #4338CA !important;
    border-radius: 4px !important;
    padding: 0.1rem 0.4rem !important;
    font-family: 'Courier New', Courier, monospace !important;
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: #F8FAFC; }
  ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

</style>
""", unsafe_allow_html=True)


# ── History helpers ────────────────────────────────────────────────────────────

def save_meeting(name: str, source_file: str, clean_text: str,
                 actions_and_questions: str, diagram_raw: str,
                 decisions_raw: str) -> str:
    ts = datetime.now()
    safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '-').lower()
    filename = f"{ts.strftime('%Y%m%d_%H%M%S')}_{safe_name}.json"
    payload = {
        "name": name,
        "source_file": source_file,
        "saved_at": ts.isoformat(),
        "clean_text": clean_text,
        "actions_and_questions": actions_and_questions,
        "diagram_raw": diagram_raw,
        "decisions_raw": decisions_raw,
    }
    (HISTORY_DIR / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return filename


def load_all_meetings() -> list:
    meetings = []
    for f in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_filename"] = f.name
            meetings.append(data)
        except Exception:
            pass
    return meetings


def delete_meeting(filename: str):
    p = HISTORY_DIR / filename
    if p.exists():
        p.unlink()


def group_by_date(meetings: list) -> dict:
    grouped = {}
    today = datetime.now().date()
    for m in meetings:
        try:
            dt = datetime.fromisoformat(m["saved_at"]).date()
        except Exception:
            dt = today
        if dt == today:
            label = "Today"
        elif (today - dt).days == 1:
            label = "Yesterday"
        else:
            label = dt.strftime("%d %b %Y")
        grouped.setdefault(label, []).append(m)
    return grouped


# ── Rendering helpers ──────────────────────────────────────────────────────────

def suggest_meeting_name(clean_text: str) -> str:
    """Ask OpenAI to suggest a short meeting name from the transcript."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=30,
        messages=[{
            "role": "user",
            "content": (
                "Suggest a short 3-6 word meeting title for this transcript. "
                "Return ONLY the title, nothing else.\n\n"
                f"{clean_text[:1000]}"
            ),
        }],
    )
    return response.choices[0].message.content.strip().strip('"')


def render_mermaid(mermaid_code: str):
    import base64
    clean = mermaid_code.strip()
    encoded = base64.urlsafe_b64encode(clean.encode("utf-8")).decode("utf-8")
    url = f"https://mermaid.ink/img/{encoded}?bgColor=white"
    st.image(url, use_container_width=True)
    live_url = f"https://mermaid.live/edit#base64:{encoded}"
    st.caption(f"[Open in Mermaid Live Editor ↗]({live_url})")


def parse_actions_md(raw: str):
    actions, questions = [], []
    actions_section = re.search(
        r'##\s*Actions?\s*\n(.*?)(?=\n##|\Z)', raw, re.DOTALL | re.IGNORECASE)
    questions_section = re.search(
        r'##\s*Open\s+Questions?\s*\n(.*?)(?=\n##|\Z)', raw, re.DOTALL | re.IGNORECASE)

    if actions_section:
        for line in actions_section.group(1).splitlines():
            line = line.strip()
            if not line or not re.match(r'[-*]', line):
                continue
            m = re.match(r'[-*]\s*\[.\]\s*\[([^\]]+)\]\s*(.+)', line)
            if m:
                actions.append({"owner": m.group(1).strip(), "text": m.group(2).strip()}); continue
            m = re.match(r'[-*]\s*\[.\]\s*\*\*([^*]+)\*\*:?\s*(.+)', line)
            if m:
                actions.append({"owner": m.group(1).strip(), "text": m.group(2).strip()}); continue
            m = re.match(r'[-*]\s*\[.\]\s*([A-Z][a-zA-Z]+):\s*(.+)', line)
            if m:
                actions.append({"owner": m.group(1).strip(), "text": m.group(2).strip()}); continue
            text = re.sub(r'^[-*]\s*\[.\]\s*', '', line).strip()
            if text:
                actions.append({"owner": "UNASSIGNED", "text": text})

    if questions_section:
        for line in questions_section.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'[-*]\s*Q:\s*(.+)', line)
            if m:
                questions.append(m.group(1).strip())
            elif re.match(r'[-*]\s+', line):
                text = re.sub(r'^[-*]\s+', '', line)
                if text:
                    questions.append(text)

    return actions, questions


def parse_decisions(raw: str) -> list:
    """Parse decisions from the decisions agent output."""
    decisions = []
    section = re.search(
        r'##\s*Decisions?\s*\n(.*?)(?=\n##|\Z)', raw, re.DOTALL | re.IGNORECASE)
    if not section:
        return decisions
    for line in section.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith('_'):
            continue
        if not re.match(r'[-*]', line):
            continue
        # Try [OWNER] format
        m = re.match(r'[-*]\s*\[([^\]]+)\]\s*(.+)', line)
        if m:
            decisions.append({"owner": m.group(1).strip(), "text": m.group(2).strip()})
        else:
            text = re.sub(r'^[-*]\s*', '', line).strip()
            if text:
                decisions.append({"owner": "TEAM", "text": text})
    return decisions


def extract_mermaid(raw: str) -> str:
    m = re.search(r'```mermaid\s*\n(.*?)```', raw, re.DOTALL)
    return m.group(1).strip() if m else raw.strip()


def agent_card(label: str, description: str, state: str) -> str:
    icon = {"waiting": "○", "running": "◉", "done": "●"}[state]
    return f"""
    <div class="agent-card {state}">
      <span class="dot"></span>
      <span><strong>{icon} {label}</strong> — {description}</span>
    </div>"""


def render_results(actions_and_questions: str, diagram_raw: str,
                   clean_text: str, decisions_raw: str = ""):
    """Render the tabbed results view."""
    actions, questions = parse_actions_md(actions_and_questions)
    decisions = parse_decisions(decisions_raw) if decisions_raw else []
    mermaid_code = extract_mermaid(diagram_raw)

    # Metrics
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Action Items", len(actions))
    m2.metric("Decisions", len(decisions))
    m3.metric("Open Questions", len(questions))
    m4.metric("Diagram Edges", mermaid_code.count("-->"))

    tab_actions, tab_decisions, tab_questions, tab_diagram, tab_transcript, tab_raw = st.tabs([
        f"✅ Actions ({len(actions)})",
        f"🟢 Decisions ({len(decisions)})",
        f"❓ Open Questions ({len(questions)})",
        "🔷 Architecture Diagram",
        "📋 Clean Transcript",
        "⚙️ Raw Output",
    ])

    with tab_actions:
        if actions:
            for a in actions:
                owner_class = "unassigned" if a["owner"].upper() == "UNASSIGNED" else ""
                st.markdown(f"""
                <div class="action-item">
                  <span class="action-owner {owner_class}">{a['owner']}</span>
                  <span>{a['text']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("No action items were identified in this meeting.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button("⬇️ Download Actions (.md)", data=actions_and_questions,
            file_name=f"actions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown")

    with tab_decisions:
        if decisions:
            for d in decisions:
                owner_class = "team" if d["owner"].upper() == "TEAM" else ""
                st.markdown(f"""
                <div class="decision-item">
                  <span class="decision-owner {owner_class}">{d['owner']}</span>
                  <span>{d['text']}</span>
                </div>""", unsafe_allow_html=True)
        elif decisions_raw:
            st.info("No decisions were recorded in this meeting.")
        else:
            st.info("Re-run the pipeline to generate decisions for this meeting.")
        if decisions_raw:
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button("⬇️ Download Decisions (.md)", data=decisions_raw,
                file_name=f"decisions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown")

    with tab_questions:
        if questions:
            for q in questions:
                st.markdown(f'<div class="question-item">❓ {q}</div>', unsafe_allow_html=True)
        else:
            st.info("No open questions were identified.")

    with tab_diagram:
        if mermaid_code:
            render_mermaid(mermaid_code)
            with st.expander("View raw Mermaid source"):
                st.code(mermaid_code, language="text")
            st.download_button("⬇️ Download Diagram (.mmd)", data=mermaid_code,
                file_name=f"diagram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mmd",
                mime="text/plain")
        else:
            st.info("No diagram was produced for this input.")

    with tab_transcript:
        st.markdown(clean_text)
        st.download_button("⬇️ Download Transcript (.md)",
            data=f"# Clean Transcript\n\n{clean_text}",
            file_name=f"clean_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown")

    with tab_raw:
        st.markdown("**Analyst Agent raw output**")
        st.code(actions_and_questions, language="markdown")
        if decisions_raw:
            st.markdown("**Decision Agent raw output**")
            st.code(decisions_raw, language="markdown")
        st.markdown("**Diagram Agent raw output**")
        st.code(diagram_raw, language="markdown")


# ── Session state init ─────────────────────────────────────────────────────────
if "loaded_meeting" not in st.session_state:
    st.session_state.loaded_meeting = None
if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "show_save" not in st.session_state:
    st.session_state.show_save = False
if "hld_mode" not in st.session_state:
    st.session_state.hld_mode = False
if "hld_bytes" not in st.session_state:
    st.session_state.hld_bytes = None
if "hld_filename" not in st.session_state:
    st.session_state.hld_filename = None
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of {"role": "user"|"assistant", "content": str}
if "agent_states" not in st.session_state:
    st.session_state.agent_states = None


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🏛️ Meeting History")
    st.markdown("---")

    if st.button("＋ New Meeting", use_container_width=True, type="primary"):
        st.session_state.loaded_meeting = None
        st.session_state.pipeline_result = None
        st.session_state.show_save = False
        st.session_state.chat_mode = False
        st.session_state.hld_mode = False
        st.rerun()

    if st.button("📄 Generate Project HLD", use_container_width=True):
        st.session_state.hld_mode = True
        st.session_state.chat_mode = False
        st.session_state.loaded_meeting = None
        st.session_state.pipeline_result = None
        st.session_state.hld_bytes = None
        st.rerun()

    if st.button("💬 Ask about your meetings", use_container_width=True):
        st.session_state.chat_mode = True
        st.session_state.hld_mode = False
        st.session_state.loaded_meeting = None
        st.session_state.pipeline_result = None
        st.rerun()

    meetings = load_all_meetings()

    if not meetings:
        st.caption("No saved meetings yet. Run the pipeline and save your first one.")
    else:
        grouped = group_by_date(meetings)
        for date_label, group in grouped.items():
            st.markdown(
                f'<div class="meeting-date-header">{date_label}</div>',
                unsafe_allow_html=True)
            for m in group:
                saved_time = datetime.fromisoformat(m["saved_at"]).strftime("%H:%M")
                col_btn, col_del = st.columns([5, 1])
                with col_btn:
                    btn_label = f"{m['name']}\n{saved_time}"
                    if st.button(btn_label, key=f"load_{m['_filename']}",
                                 use_container_width=True):
                        st.session_state.loaded_meeting = m
                        st.session_state.pipeline_result = None
                        st.session_state.show_save = False
                        st.rerun()
                with col_del:
                    if st.session_state.get(f"confirm_del_{m['_filename']}"):
                        st.markdown("<small style='color:#EF4444'>Sure?</small>", unsafe_allow_html=True)
                        yes_col, no_col = st.columns(2)
                        with yes_col:
                            if st.button("✓", key=f"yes_del_{m['_filename']}", help="Yes, delete"):
                                delete_meeting(m["_filename"])
                                if (st.session_state.loaded_meeting and
                                        st.session_state.loaded_meeting.get("_filename") == m["_filename"]):
                                    st.session_state.loaded_meeting = None
                                st.session_state[f"confirm_del_{m['_filename']}"] = False
                                st.rerun()
                        with no_col:
                            if st.button("✕", key=f"no_del_{m['_filename']}", help="Cancel"):
                                st.session_state[f"confirm_del_{m['_filename']}"] = False
                                st.rerun()
                    else:
                        if st.button("✕", key=f"del_{m['_filename']}", help="Delete this meeting"):
                            st.session_state[f"confirm_del_{m['_filename']}"] = True
                            st.rerun()


# ── Main area ──────────────────────────────────────────────────────────────────

# Case 0: Chat with your meetings
if st.session_state.chat_mode:
    meetings = load_all_meetings()

    st.markdown("""
    <div class="header-block">
      <h1>💬 Ask about your meetings</h1>
      <p>Ask anything across all your saved meetings — decisions, actions, open questions, architecture.</p>
    </div>""", unsafe_allow_html=True)

    if not meetings:
        st.warning("No saved meetings yet. Run the pipeline on some transcripts first.")
        if st.button("← Back"):
            st.session_state.chat_mode = False
            st.rerun()
    else:
        # Build meeting context for system prompt
        def build_meeting_context(meetings: list) -> str:
            blocks = []
            for m in meetings:
                saved_at = datetime.fromisoformat(m["saved_at"]).strftime("%d %b %Y %H:%M")
                blocks.append(f"""
=== Meeting: {m['name']} ({saved_at}) ===

CLEAN TRANSCRIPT:
{m.get('clean_text', '')}

ACTIONS & QUESTIONS:
{m.get('actions_and_questions', '')}

DECISIONS:
{m.get('decisions_raw', '')}

ARCHITECTURE DIAGRAM (Mermaid):
{m.get('diagram_raw', '')}
""")
            return "\n".join(blocks)

        CHAT_SYSTEM_PROMPT = """You are an expert assistant with full knowledge of the meeting notes, 
decisions, actions, and architecture discussions from the user's saved meetings.

Answer questions clearly and concisely, referencing specific meetings by name where relevant.
Format responses in plain prose where possible. Use bullet points sparingly.
Avoid large headings — use bold text instead for emphasis.
When listing items like actions or decisions, format them clearly.
If something wasn't discussed in any meeting, say so honestly rather than guessing.
Be direct and professional — your audience are architects and technical leads."""

        # Display chat history
        if not st.session_state.chat_history:
            st.markdown("""
            <div class="chat-empty">
              <div class="icon">💬</div>
              <div class="title">Ask anything about your meetings</div>
              <div class="subtitle">Try one of these to get started</div>
            </div>""", unsafe_allow_html=True)

            # Suggestion buttons
            suggestions = [
                "What decisions have been made so far?",
                "Which actions are still unassigned?",
                "What are the main open questions?",
                "Summarise the architecture discussed",
                "What were the key risks identified?",
            ]
            cols = st.columns(len(suggestions))
            for i, (col, suggestion) in enumerate(zip(cols, suggestions)):
                with col:
                    if st.button(suggestion, key=f"suggest_{i}",
                                 use_container_width=True):
                        st.session_state.chat_history.append({
                            "role": "user", "content": suggestion
                        })
                        st.rerun()
        else:
            # Render conversation
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"""
                    <div class="chat-message user">
                      <div class="chat-avatar user">You</div>
                      <div class="chat-bubble user">{msg['content']}</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="chat-message assistant">
                      <div class="chat-avatar assistant">🏛️</div>
                      <div class="chat-bubble assistant">{msg['content']}</div>
                    </div>""", unsafe_allow_html=True)

        # If last message is from user, get assistant response
        if (st.session_state.chat_history and
                st.session_state.chat_history[-1]["role"] == "user"):
            with st.spinner("Thinking..."):
                try:
                    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

                    meeting_context = build_meeting_context(meetings)
                    full_system = f"{CHAT_SYSTEM_PROMPT}\n\n## Your Meeting Data\n{meeting_context}"

                    # Build messages for API (exclude any stale assistant placeholders)
                    api_messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_history
                    ]

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        max_tokens=1024,
                        messages=[{"role": "system", "content": full_system}] + api_messages,
                    )
                    reply = response.choices[0].message.content
                    st.session_state.chat_history.append({
                        "role": "assistant", "content": reply
                    })
                    st.rerun()

                except Exception as e:
                    st.error(f"Chat error: {e}")

        # Input box always at the bottom
        st.markdown("<br>", unsafe_allow_html=True)
        input_col, btn_col = st.columns([5, 1])
        with input_col:
            user_input = st.text_input(
                "Ask a question",
                placeholder="e.g. What decisions have we made about the auth service?",
                label_visibility="collapsed",
                key="chat_input",
            )
        with btn_col:
            send = st.button("Send →", type="primary", use_container_width=True)

        if send and user_input.strip():
            st.session_state.chat_history.append({
                "role": "user", "content": user_input.strip()
            })
            st.rerun()

        # Clear chat button
        if st.session_state.chat_history:
            if st.button("🗑 Clear conversation", use_container_width=False):
                st.session_state.chat_history = []
                st.rerun()

# Case 1: HLD mode
elif st.session_state.hld_mode:
    st.markdown("""
    <div class="header-block">
      <h1>📄 Generate Project HLD</h1>
      <p>Select meetings to include, name your project, and generate a synthesised HLD document.</p>
    </div>""", unsafe_allow_html=True)

    meetings = load_all_meetings()

    if not meetings:
        st.warning("No saved meetings yet. Run the pipeline on some transcripts first.")
        if st.button("← Back"):
            st.session_state.hld_mode = False
            st.rerun()
    else:
        st.markdown("#### 1. Select meetings to include")
        selected = []
        for m in meetings:
            saved_at = datetime.fromisoformat(m["saved_at"]).strftime("%d %b %Y %H:%M")
            if st.checkbox(f"**{m['name']}** — {saved_at}",
                           key=f"hld_select_{m['_filename']}", value=True):
                selected.append(m)

        st.markdown("#### 2. Name your project")
        project_name = st.text_input(
            "Project name",
            placeholder="e.g. Zeos Integration — Microservices Migration",
            label_visibility="collapsed",
        )

        st.markdown("---")
        gen_col, back_col = st.columns([2, 1])
        with gen_col:
            generate = st.button(
                "⚡ Generate HLD", type="primary", use_container_width=True,
                disabled=len(selected) == 0 or not project_name.strip(),
            )
        with back_col:
            if st.button("← Cancel", use_container_width=True):
                st.session_state.hld_mode = False
                st.rerun()

        if generate:
            with st.spinner(f"Synthesising {len(selected)} meeting(s) into HLD..."):
                try:
                    from agents.hld import generate_hld_from_meetings
                    from agents.hld_docx import render_hld_docx

                    hld_content = generate_hld_from_meetings(
                        meetings=selected,
                        project_name=project_name.strip(),
                    )
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                        render_hld_docx(hld_content, tmp.name)
                        tmp_path = tmp.name
                    with open(tmp_path, "rb") as f:
                        docx_bytes = f.read()
                    Path(tmp_path).unlink(missing_ok=True)

                    safe_title = re.sub(r'[^\w\s-]', '', project_name).replace(' ', '-').lower()
                    filename = f"{safe_title}-hld-{datetime.now().strftime('%Y%m%d')}.docx"
                    st.session_state.hld_bytes = docx_bytes
                    st.session_state.hld_filename = filename
                    st.rerun()
                except Exception as e:
                    st.error(f"HLD generation failed: {e}")
                    raise

        if st.session_state.hld_bytes:
            st.success(f"✅ HLD generated from {len(selected)} meeting(s)")
            st.download_button(
                "⬇️ Download HLD (.docx)",
                data=st.session_state.hld_bytes,
                file_name=st.session_state.hld_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

# Case 3: Viewing a saved meeting
elif st.session_state.loaded_meeting:
    m = st.session_state.loaded_meeting
    saved_at = datetime.fromisoformat(m["saved_at"]).strftime("%d %b %Y at %H:%M")
    st.markdown(f"""
    <div class="header-block">
      <h1>📋 {m['name']}</h1>
      <p>Saved {saved_at} · {m.get('source_file', 'unknown source')}</p>
    </div>""", unsafe_allow_html=True)
    render_results(
        m["actions_and_questions"],
        m["diagram_raw"],
        m["clean_text"],
        m.get("decisions_raw", ""),  # backwards compatible with older saved meetings
    )

# Case 4: Fresh pipeline result
elif st.session_state.pipeline_result:
    r = st.session_state.pipeline_result
    st.markdown("""
    <div class="header-block">
      <h1>🏛️ Meeting Artefact Pipeline</h1>
      <p>Pipeline complete — save this meeting or review below.</p>
    </div>""", unsafe_allow_html=True)

    if st.session_state.show_save:
        st.markdown("#### 💾 Save this meeting")
        save_col, btn_col, skip_col = st.columns([3, 1, 1])
        with save_col:
            if "suggested_name" not in st.session_state:
                try:
                    suggested = suggest_meeting_name(r["clean_text"])
                except Exception:
                    suggested = ""
                ts = datetime.now().strftime("%d-%m-%Y %H:%M")
                st.session_state.suggested_name = f"{suggested} — {ts}" if suggested else ts

            meeting_name = st.text_input(
                "Meeting name",
                value=st.session_state.suggested_name,
                label_visibility="collapsed",
            )
        with btn_col:
            if st.button("Save", type="primary", use_container_width=True):
                if meeting_name.strip():
                    fname = save_meeting(
                        name=meeting_name.strip(),
                        source_file=r["source_file"],
                        clean_text=r["clean_text"],
                        actions_and_questions=r["actions_and_questions"],
                        diagram_raw=r["diagram_raw"],
                        decisions_raw=r["decisions_raw"],
                    )
                    saved = json.loads((HISTORY_DIR / fname).read_text(encoding="utf-8"))
                    saved["_filename"] = fname
                    st.session_state.loaded_meeting = saved
                    st.session_state.pipeline_result = None
                    st.session_state.show_save = False
                    st.session_state.pop("suggested_name", None)
                    st.rerun()
                else:
                    st.warning("Please enter a name.")
        with skip_col:
            if st.button("Skip", use_container_width=True):
                st.session_state.show_save = False
                st.session_state.pop("suggested_name", None)
                st.rerun()
        st.markdown("---")

    render_results(
        r["actions_and_questions"],
        r["diagram_raw"],
        r["clean_text"],
        r["decisions_raw"],
    )

# Case 5: Upload screen
else:
    st.markdown("""
    <div class="header-block">
      <h1>🏛️ Meeting Artefact Pipeline</h1>
      <p>Drop in a transcript, notes, or voice recording — get back structured actions, decisions, and an architecture diagram.</p>
    </div>""", unsafe_allow_html=True)

    col_upload, col_info = st.columns([2, 1])
    with col_upload:
        uploaded_file = st.file_uploader(
            "Upload your meeting file",
            type=["txt", "md", "m4a", "mp3", "wav"],
        )
    with col_info:
        st.markdown("""
        **Supported inputs**
        - 📄 `.txt` — raw transcript
        - 📝 `.md` — meeting notes
        - 🎙️ `.m4a / .mp3 / .wav` — voice recording

        **What you'll get**
        - ✅ Action items with owners
        - 🟢 Decisions log
        - 🔷 Architecture diagram
        - ❓ Open questions
        - 📋 Clean transcript
        """)

    if uploaded_file:
        suffix = Path(uploaded_file.name).suffix.lower()
        is_audio = suffix in [".m4a", ".mp3", ".wav"]
        source_type = "audio" if is_audio else ("notes" if suffix == ".md" else "transcript")

        with col_upload:
            _, btn_col = st.columns([5, 1])
            with btn_col:
                run = st.button("⚡ Run Pipeline", type="primary", use_container_width=True)

        if run:
            st.markdown("---")
            progress_placeholder = st.empty()
            st.session_state.agent_states = {
                "ingestion": "waiting",
                "analyst": "waiting",
                "decisions": "waiting",
                "diagram": "waiting",
            }

            def render_progress():
                with progress_placeholder.container():
                    if st.session_state.agent_states:
                        st.markdown("#### Pipeline Progress")
                        html = (
                            agent_card("Ingestion Agent",  "Normalising raw input",           st.session_state.agent_states["ingestion"])
                            + agent_card("Analyst Agent",  "Extracting actions & questions",  st.session_state.agent_states["analyst"])
                            + agent_card("Decision Agent", "Identifying decisions made",      st.session_state.agent_states["decisions"])
                            + agent_card("Diagram Agent",  "Generating architecture diagram", st.session_state.agent_states["diagram"])
                        )
                        st.markdown(html, unsafe_allow_html=True)
                        st.markdown("---")

            render_progress()

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            try:
                from agents.ingestion import ingest, transcribe_audio
                from agents.analyst import analyse
                from agents.diagram import generate_diagram
                from agents.decisions import extract_decisions

                st.session_state.agent_states["ingestion"] = "running"; render_progress()
                raw_input = tmp_path if is_audio else Path(tmp_path).read_text(encoding="utf-8")
                if is_audio:
                    raw_input = transcribe_audio(tmp_path)
                clean_text = ingest(raw_input, source_type)
                st.session_state.agent_states["ingestion"] = "done"; render_progress()

                st.session_state.agent_states["analyst"] = "running"; render_progress()
                actions_and_questions = analyse(clean_text)
                st.session_state.agent_states["analyst"] = "done"; render_progress()

                st.session_state.agent_states["decisions"] = "running"; render_progress()
                decisions_raw = extract_decisions(clean_text)
                st.session_state.agent_states["decisions"] = "done"; render_progress()

                st.session_state.agent_states["diagram"] = "running"; render_progress()
                diagram_raw = generate_diagram(clean_text)
                st.session_state.agent_states["diagram"] = "done"; render_progress()

                st.session_state.pipeline_result = {
                    "source_file": uploaded_file.name,
                    "clean_text": clean_text,
                    "actions_and_questions": actions_and_questions,
                    "decisions_raw": decisions_raw,
                    "diagram_raw": diagram_raw,
                }
                st.session_state.pop("suggested_name", None)
                st.session_state.show_save = True
                st.rerun()

            except ImportError as e:
                st.error(f"Could not import pipeline modules: {e}")
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                raise
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    else:
        st.markdown("""
        <div style="text-align:center; padding: 4rem 2rem;">
          <div style="font-size: 3rem; margin-bottom: 1rem; opacity:0.25;">🎙️</div>
          <div style="font-size: 0.88rem; font-weight: 500; color: #94A3B8;
               font-family: 'Courier New', Courier, monospace; letter-spacing: 0.5px;">
            Upload a file above to get started
          </div>
        </div>""", unsafe_allow_html=True)
