"""
app.py — Streamlit UI for the Meeting-to-Artefact Pipeline
Drop alongside pipeline.py in the project root and run:
    streamlit run app.py
"""

import re
import json
import os
import tempfile
import html
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from agents.redaction import parse_sensitive_terms, tokenize_sensitive_text

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
REDACTION_LABELS = {
    "PERSON": "people",
    "ORG": "organisations",
    "EMAIL": "emails",
    "PHONE": "phone numbers",
    "URL": "URLs",
    "IP": "IP addresses",
    "TERM": "custom terms",
}

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
  [data-testid="stSpinner"] * {
    color: #0F172A !important;
  }
  [data-testid="stSelectbox"] label p,
  [data-testid="stTextInput"] label p,
  [data-testid="stMultiSelect"] label p {
    color: #0F172A !important;
  }

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
  [data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #6366F1 !important;
    border: 1px solid #6366F1 !important;
    color: #FFFFFF !important;
    box-shadow: 0 10px 30px rgba(99,102,241,0.16) !important;
  }
  [data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
    background: #4F46E5 !important;
    border-color: #4F46E5 !important;
    color: #FFFFFF !important;
    box-shadow: 0 12px 28px rgba(79,70,229,0.22) !important;
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
  .agent-card.skipped {
    background: #FFFBEB; color: #B45309;
    border-color: #FDE68A;
  }
  /* Status badges */
  .status-open {
    background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE;
    padding: 0.15rem 0.6rem; border-radius: 4px; font-size: 0.72rem;
    font-family: 'Courier New', monospace; font-weight: 500;
  }
  .status-progress {
    background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A;
    padding: 0.15rem 0.6rem; border-radius: 4px; font-size: 0.72rem;
    font-family: 'Courier New', monospace; font-weight: 500;
  }
  .status-done {
    background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0;
    padding: 0.15rem 0.6rem; border-radius: 4px; font-size: 0.72rem;
    font-family: 'Courier New', monospace; font-weight: 500;
  }
  /* Inline status selectbox */
  [data-testid="stSelectbox"] > div > div {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    font-size: 0.95rem !important;
    color: #475569 !important;
    height: 52px !important;
    min-height: 52px !important;
    box-sizing: border-box !important;
  }
  .agent-card .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .agent-card.waiting .dot { background: #CBD5E1; }
  .agent-card.running .dot {
    background: #3B82F6;
    animation: pulse-ring 1.2s infinite;
  }
  .agent-card.done .dot { background: #16A34A; }
  .agent-card.skipped .dot { background: #D97706; }
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
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0 1rem; border-radius: 8px; margin-bottom: 0.5rem;
    min-height: 52px;
    box-sizing: border-box;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 3px solid #6366F1;
    font-size: 1rem; color: #1E293B;
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
    background: #FFFFFF;
    border: 1px solid #FDE68A;
    border-left: 3px solid #F59E0B;
    font-size: 1rem; color: #1E293B;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }

  .decision-item {
    display: flex; align-items: flex-start; gap: 0.75rem;
    padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;
    background: #FFFFFF;
    border: 1px solid #BBF7D0;
    border-left: 3px solid #16A34A;
    font-size: 1rem; color: #1E293B;
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

st.markdown("""
<style>
  :root {
    --bg: #f5f5f7;
    --bg-alt: #edf1f5;
    --surface: rgba(255, 255, 255, 0.78);
    --surface-strong: rgba(255, 255, 255, 0.94);
    --border: rgba(15, 23, 42, 0.08);
    --text: #111827;
    --muted: #6b7280;
    --muted-strong: #4b5563;
    --accent: #0071e3;
    --shadow-soft: 0 18px 42px rgba(15, 23, 42, 0.07);
    --shadow-card: 0 10px 26px rgba(15, 23, 42, 0.06);
    --radius-xl: 32px;
  }

  html, body, [class*="css"] {
    font-family: "SF Pro Text", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: var(--text);
  }

  .stApp {
    background:
      radial-gradient(circle at top left, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0) 32%),
      radial-gradient(circle at top right, rgba(225, 238, 255, 0.86), rgba(225, 238, 255, 0) 26%),
      linear-gradient(180deg, #fbfbfd 0%, var(--bg) 54%, var(--bg-alt) 100%) !important;
  }

  .block-container {
    max-width: 1380px;
    padding-top: 1.2rem !important;
    padding-right: 2rem !important;
    padding-bottom: 2rem !important;
  }

  header[data-testid="stHeader"] {
    background: rgba(245, 245, 247, 0.55) !important;
    backdrop-filter: blur(18px);
    border-bottom: 1px solid var(--border);
  }

  [data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.72) !important;
    backdrop-filter: blur(24px);
    border-right: 1px solid var(--border) !important;
  }

  section[data-testid="stSidebar"] {
    width: 310px !important;
    min-width: 310px !important;
  }

  section[data-testid="stSidebar"] > div:first-child {
    width: 310px !important;
    min-width: 310px !important;
    padding-top: 1rem !important;
    padding-left: 0.9rem !important;
    padding-right: 0.9rem !important;
  }

  .sidebar-brand {
    padding: 0.3rem 0.15rem 0.95rem 0.15rem;
  }

  .sidebar-kicker,
  .page-kicker {
    text-transform: uppercase;
    letter-spacing: 0.22em;
    font-size: 0.7rem;
    color: var(--muted);
    font-weight: 700;
  }

  .sidebar-brand h1 {
    margin: 0.42rem 0 0.2rem 0;
    font-size: 1.55rem;
    line-height: 1.05;
    letter-spacing: -0.04em;
    color: var(--text);
  }

  .sidebar-brand p {
    margin: 0;
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.45;
  }

  [data-testid="stSidebar"] hr {
    margin: 0.95rem 0 !important;
    border-top: 1px solid var(--border) !important;
  }

  [data-testid="stSidebar"] .stButton button {
    background: rgba(255, 255, 255, 0.64) !important;
    border: 1px solid var(--border) !important;
    color: var(--muted-strong) !important;
    border-radius: 16px !important;
    min-height: 48px !important;
    padding: 0.72rem 1rem !important;
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
    box-shadow: none !important;
  }

  [data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255, 255, 255, 0.94) !important;
    border-color: rgba(0, 113, 227, 0.28) !important;
    color: var(--text) !important;
    transform: translateY(-1px);
  }

  [data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: linear-gradient(180deg, #1f2937, #111827) !important;
    border-color: rgba(17, 24, 39, 0.95) !important;
    color: #ffffff !important;
    border-radius: 999px !important;
    box-shadow: 0 14px 30px rgba(17, 24, 39, 0.16) !important;
  }

  [data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
    background: linear-gradient(180deg, #111827, #030712) !important;
    border-color: rgba(17, 24, 39, 1) !important;
  }

  .page-hero {
    position: relative;
    overflow: hidden;
    padding: 1.45rem 1.55rem 1.5rem;
    margin-bottom: 1.35rem;
    border-radius: var(--radius-xl);
    border: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.58));
    box-shadow: var(--shadow-soft);
    backdrop-filter: blur(22px);
  }

  .page-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle at top right, rgba(0, 113, 227, 0.12), rgba(0, 113, 227, 0) 24%),
      linear-gradient(135deg, rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0));
    pointer-events: none;
  }

  .page-hero > * {
    position: relative;
    z-index: 1;
  }

  .header-block {
    position: relative;
    overflow: hidden;
    padding: 1.45rem 1.55rem 1.5rem;
    margin-bottom: 1.35rem;
    border-radius: var(--radius-xl);
    border: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.58));
    box-shadow: var(--shadow-soft);
    backdrop-filter: blur(22px);
  }

  .header-block::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle at top right, rgba(0, 113, 227, 0.12), rgba(0, 113, 227, 0) 24%),
      linear-gradient(135deg, rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0));
    pointer-events: none;
  }

  .header-block h1 {
    position: relative;
    z-index: 1;
    margin: 0;
    font-size: clamp(2.1rem, 4vw, 3.2rem);
    line-height: 0.98;
    letter-spacing: -0.065em;
    color: var(--text);
  }

  .header-block p {
    position: relative;
    z-index: 1;
    margin: 0.75rem 0 0 0;
    max-width: 58rem;
    font-size: 1rem;
    line-height: 1.55;
    color: var(--muted);
  }

  .hero-meta {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1rem;
    padding: 0.48rem 0.82rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: rgba(248, 250, 252, 0.9);
    color: var(--muted-strong);
    font-size: 0.84rem;
    font-weight: 500;
  }

  .info-panel,
  .upload-empty-state {
    border-radius: 28px;
    border: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(248, 250, 252, 0.72));
    box-shadow: var(--shadow-card);
  }

  .info-panel {
    padding: 1.3rem 1.35rem;
  }

  .info-panel h3,
  .upload-empty-state h3 {
    margin: 0.42rem 0 0.45rem 0;
    font-size: 1.3rem;
    line-height: 1.15;
    letter-spacing: -0.035em;
    color: var(--text);
  }

  .info-panel p,
  .upload-empty-state p {
    margin: 0;
    color: var(--muted);
    line-height: 1.55;
  }

  .info-list {
    margin-top: 1.05rem;
    display: grid;
    gap: 0.8rem;
  }

  .info-row {
    padding-top: 0.8rem;
    border-top: 1px solid rgba(15, 23, 42, 0.06);
  }

  .info-label {
    display: block;
    margin-bottom: 0.2rem;
    color: var(--muted);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .info-copy {
    color: var(--text);
    font-size: 0.96rem;
    line-height: 1.55;
  }

  .upload-empty-state {
    padding: 2.15rem 1.4rem;
    text-align: center;
    margin-top: 1rem;
  }

  .upload-empty-state .upload-glyph {
    width: 72px;
    height: 72px;
    margin: 0 auto 1rem auto;
    border-radius: 22px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(235, 245, 255, 0.78));
    border: 1px solid rgba(0, 113, 227, 0.12);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: var(--accent);
  }

  [data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.8) !important;
    border: 1px solid var(--border) !important;
    border-radius: 24px !important;
    box-shadow: var(--shadow-card);
    padding: 1.12rem 1.25rem !important;
  }

  [data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    letter-spacing: 0.14em;
    font-size: 0.72rem !important;
  }

  [data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-size: 2.35rem !important;
    letter-spacing: -0.06em !important;
  }

  [data-testid="stTabs"],
  .stTabs [data-baseweb="tab-list"],
  div[role="tablist"] {
    border: 0 !important;
    background: transparent !important;
  }

  .stTabs [data-baseweb="tab-list"],
  div[role="tablist"] {
    width: fit-content;
    padding: 0.35rem;
    gap: 0.35rem !important;
    border-radius: 999px;
    box-shadow: inset 0 0 0 1px var(--border);
    background: rgba(255, 255, 255, 0.72) !important;
    margin-bottom: 1.2rem !important;
  }

  [data-testid="stTabs"] button,
  .stTabs [data-baseweb="tab"] {
    border-radius: 999px !important;
    padding: 0.62rem 1rem !important;
    color: var(--muted) !important;
  }

  [data-testid="stTabs"] button[aria-selected="true"],
  .stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(255, 255, 255, 0.98) !important;
    color: var(--text) !important;
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
  }

  .stTabs [data-baseweb="tab-highlight"] {
    background: transparent !important;
  }

  .action-item,
  .decision-item,
  .question-item,
  .agent-card {
    border-radius: 20px !important;
    border: 1px solid var(--border) !important;
    background: rgba(255, 255, 255, 0.84) !important;
    box-shadow: var(--shadow-card);
  }

  .action-item,
  .decision-item,
  .question-item {
    padding: 1rem 1.1rem !important;
    margin-bottom: 0.7rem;
    border-left: 0 !important;
  }

  .action-item {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(240, 247, 255, 0.88)) !important;
  }

  .decision-item {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(240, 253, 245, 0.86)) !important;
  }

  .question-item {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 250, 240, 0.88)) !important;
  }

  .action-owner,
  .decision-owner {
    border-radius: 999px !important;
    padding: 0.26rem 0.72rem !important;
    font-family: "SF Mono", "SFMono-Regular", Consolas, monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.02em;
  }

  .action-owner {
    background: rgba(0, 113, 227, 0.1) !important;
    color: #0356ab !important;
  }

  .action-owner.unassigned {
    background: rgba(107, 114, 128, 0.12) !important;
    color: var(--muted-strong) !important;
  }

  .decision-owner,
  .decision-owner.team {
    background: rgba(20, 128, 74, 0.12) !important;
    color: #106238 !important;
  }

  .agent-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.95rem 1.05rem !important;
    margin-bottom: 0.55rem;
  }

  .agent-card-copy {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    min-width: 0;
  }

  .agent-card-title {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    color: var(--text);
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  .agent-card-description {
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.45;
  }

  .agent-card-state {
    flex-shrink: 0;
    padding: 0.32rem 0.62rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border: 1px solid transparent;
  }

  .agent-card.waiting .agent-card-state {
    color: var(--muted);
    background: rgba(107, 114, 128, 0.08);
    border-color: rgba(107, 114, 128, 0.12);
  }

  .agent-card.running .agent-card-state {
    color: #0356ab;
    background: rgba(0, 113, 227, 0.09);
    border-color: rgba(0, 113, 227, 0.16);
  }

  .agent-card.done .agent-card-state {
    color: #106238;
    background: rgba(20, 128, 74, 0.1);
    border-color: rgba(20, 128, 74, 0.15);
  }

  .agent-card.skipped .agent-card-state {
    color: #9a6700;
    background: rgba(185, 119, 14, 0.11);
    border-color: rgba(185, 119, 14, 0.16);
  }

  .agent-card .dot {
    width: 10px;
    height: 10px;
  }

  [data-testid="stSelectbox"] > div > div,
  [data-testid="stTextInput"] input,
  [data-testid="stTextArea"] textarea,
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background: rgba(255, 255, 255, 0.86) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    color: var(--text) !important;
    box-shadow: none !important;
  }

  [data-testid="stSelectbox"] > div > div {
    min-height: 52px !important;
  }

  [data-testid="stTextInput"] input,
  [data-testid="stTextArea"] textarea {
    padding-left: 0.9rem !important;
  }

  [data-testid="stTextInput"] input:focus,
  [data-testid="stTextArea"] textarea:focus {
    border-color: rgba(0, 113, 227, 0.32) !important;
    box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.08) !important;
  }

  [data-testid="stFileUploader"],
  [data-testid="stFileUploaderDropzone"] {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(248, 250, 252, 0.82)) !important;
    border: 1.5px dashed rgba(15, 23, 42, 0.14) !important;
    border-radius: 28px !important;
  }

  [data-testid="stFileUploader"]:hover {
    border-color: rgba(0, 113, 227, 0.28) !important;
  }

  .stButton button[kind="primary"] {
    background: linear-gradient(180deg, #1f2937, #111827) !important;
    border: 1px solid rgba(17, 24, 39, 0.95) !important;
    color: #ffffff !important;
    border-radius: 999px !important;
    box-shadow: 0 14px 30px rgba(17, 24, 39, 0.16) !important;
  }

  .stButton button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 18px 36px rgba(17, 24, 39, 0.2) !important;
  }

  .stButton button[kind="secondary"],
  [data-testid="stDownloadButton"] button {
    background: rgba(255, 255, 255, 0.82) !important;
    border: 1px solid var(--border) !important;
    color: var(--muted-strong) !important;
    border-radius: 999px !important;
    box-shadow: none !important;
  }

  .stButton button[kind="secondary"]:hover,
  [data-testid="stDownloadButton"] button:hover {
    border-color: rgba(0, 113, 227, 0.24) !important;
    color: var(--text) !important;
    background: rgba(255, 255, 255, 0.96) !important;
  }

  [data-testid="stAlert"] {
    background: rgba(255, 255, 255, 0.82) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
    box-shadow: var(--shadow-card);
  }

  [data-testid="stCode"],
  [data-testid="stExpander"] {
    background: rgba(255, 255, 255, 0.78) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
  }

  .chat-avatar.user,
  .chat-bubble.user {
    background: linear-gradient(180deg, #1f2937, #111827) !important;
  }

  .chat-avatar.assistant {
    background: rgba(255, 255, 255, 0.92) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
  }

  .chat-bubble.assistant {
    background: rgba(255, 255, 255, 0.88) !important;
    border-color: var(--border) !important;
    box-shadow: var(--shadow-card);
  }

  .chat-suggestion {
    background: rgba(255, 255, 255, 0.82) !important;
    border: 1px solid var(--border) !important;
    color: var(--muted-strong) !important;
  }

  .chat-suggestion:hover {
    background: rgba(255, 255, 255, 0.96) !important;
    border-color: rgba(0, 113, 227, 0.22) !important;
    color: var(--text) !important;
  }

  @media (max-width: 960px) {
    .block-container {
      padding-left: 1rem !important;
      padding-right: 1rem !important;
      padding-top: 0.85rem !important;
    }

    .page-hero {
      padding: 1.1rem 1rem 1.15rem;
      border-radius: 24px;
    }

    .header-block h1 {
      font-size: 2rem;
    }
  }
</style>
""", unsafe_allow_html=True)


def save_meeting(name: str, source_file: str, clean_text: str,
                 actions_and_questions: str, diagram_raw: str,
                 decisions_raw: str, redaction: dict | None = None) -> str:
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
        "redaction": redaction or {"mode": "off", "counts": {}, "custom_term_count": 0},
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


def get_statuses(filename: str) -> dict:
    """Load status dict from a saved meeting JSON. Returns empty dict if not found."""
    if not filename:
        return {}
    p = HISTORY_DIR / filename
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("statuses", {})
    except Exception:
        return {}


def save_status(filename: str, item_type: str, item_index: int, status: str):
    """Persist a status change back to the meeting JSON file."""
    if not filename:
        return
    p = HISTORY_DIR / filename
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if "statuses" not in data:
            data["statuses"] = {}
        if item_type not in data["statuses"]:
            data["statuses"][item_type] = {}
        data["statuses"][item_type][str(item_index)] = status
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def delete_meeting(filename: str):
    p = HISTORY_DIR / filename
    if p.exists():
        p.unlink()


def format_redaction_summary(redaction: dict | None) -> str:
    """Format a human-readable redaction summary for banners and headers."""
    if not redaction or redaction.get("mode") != "tokenize":
        return ""

    counts = redaction.get("counts", {})
    parts = [
        f"{counts[label]} {name}"
        for label, name in REDACTION_LABELS.items()
        if counts.get(label)
    ]
    if not parts:
        return "Sensitive text was tokenized before analysis and save."
    return "Sensitive text was tokenized before analysis and save: " + ", ".join(parts) + "."


def render_redaction_notice(redaction: dict | None):
    """Show a concise note when tokenization was applied to this meeting."""
    message = format_redaction_summary(redaction)
    if message:
        st.info(message)


def render_page_header(title: str, subtitle: str, eyebrow: str = "Meeting Artefact Pipeline",
                       meta: str = ""):
    """Render a consistent top-level page header."""
    meta_html = f'<div class="hero-meta">{html.escape(meta)}</div>' if meta else ""
    st.markdown(
        f"""
        <section class="page-hero">
          <div class="page-kicker">{html.escape(eyebrow)}</div>
          <div class="header-block">
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
          </div>
          {meta_html}
        </section>
        """,
        unsafe_allow_html=True,
    )


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
    url = f"https://mermaid.ink/img/{encoded}?bgColor=white&width=900"
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


def split_action_text_and_deadline(text: str) -> tuple[str, str]:
    """Split an action into its main text and trailing markdown deadline, if present."""
    m = re.match(r"^(.*?)\s*_\((.+?)\)_\s*$", text.strip())
    if not m:
        return text.strip(), ""
    return m.group(1).strip(), m.group(2).strip()


def next_weekday(reference_date, target_weekday: int, force_next_week: bool = False):
    """Return the next occurrence of a weekday relative to a reference date."""
    days_ahead = target_weekday - reference_date.weekday()
    if days_ahead < 0 or force_next_week:
        days_ahead += 7
    return reference_date + timedelta(days=days_ahead)


def infer_due_date(deadline_text: str, reference_dt: datetime):
    """Infer a due date from simple relative deadline phrasing."""
    if not deadline_text:
        return None

    text = deadline_text.strip().lower()
    ref_date = reference_dt.date()

    if "today" in text:
        return ref_date
    if "tomorrow" in text:
        return ref_date + timedelta(days=1)
    if "in two weeks" in text or "in 2 weeks" in text:
        return ref_date + timedelta(days=14)
    if "in one week" in text or "in 1 week" in text:
        return ref_date + timedelta(days=7)
    if "end of next week" in text:
        next_monday = next_weekday(ref_date, 0, force_next_week=True)
        return next_monday + timedelta(days=4)
    if "next week" in text or "following week" in text:
        return ref_date + timedelta(days=7)
    if "end of week" in text:
        return next_weekday(ref_date, 4)

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for weekday_name, weekday_num in weekdays.items():
        if weekday_name in text:
            force_next = f"next {weekday_name}" in text
            return next_weekday(ref_date, weekday_num, force_next_week=force_next)

    return None


def classify_due_bucket(due_date, status: str, today=None) -> str:
    """Classify an inferred due date into a dashboard-friendly bucket."""
    if status == "Done":
        return "Done"
    if due_date is None:
        return "No deadline"
    today = today or datetime.now().date()
    delta_days = (due_date - today).days
    if delta_days < 0:
        return "Overdue"
    if delta_days <= 7:
        return "Due soon"
    return "Upcoming"


def build_action_records(meetings: list) -> list:
    """Build a flattened cross-meeting action list with persisted statuses."""
    records = []
    for meeting in meetings:
        actions, _ = parse_actions_md(meeting.get("actions_and_questions", ""))
        statuses = get_statuses(meeting.get("_filename", ""))
        try:
            saved_at = datetime.fromisoformat(meeting["saved_at"])
        except Exception:
            saved_at = datetime.now()

        for i, action in enumerate(actions):
            action_text, deadline = split_action_text_and_deadline(action["text"])
            status = statuses.get("actions", {}).get(str(i), "Open")
            due_date = infer_due_date(deadline, saved_at)
            records.append({
                "meeting_name": meeting.get("name", "Untitled Meeting"),
                "meeting_filename": meeting.get("_filename", ""),
                "meeting_saved_at": saved_at,
                "owner": action["owner"],
                "text": action_text,
                "deadline": deadline,
                "status": status,
                "due_date": due_date,
                "due_bucket": classify_due_bucket(due_date, status),
                "action_index": i,
            })
    return records


def build_decision_records(meetings: list) -> list:
    """Build a flattened cross-meeting decision list with persisted statuses."""
    records = []
    for meeting in meetings:
        decisions = parse_decisions(meeting.get("decisions_raw", ""))
        statuses = get_statuses(meeting.get("_filename", ""))
        try:
            saved_at = datetime.fromisoformat(meeting["saved_at"])
        except Exception:
            saved_at = datetime.now()

        for i, decision in enumerate(decisions):
            records.append({
                "meeting_name": meeting.get("name", "Untitled Meeting"),
                "meeting_filename": meeting.get("_filename", ""),
                "meeting_saved_at": saved_at,
                "owner": decision["owner"],
                "text": decision["text"],
                "status": statuses.get("decisions", {}).get(str(i), "Open"),
                "decision_index": i,
            })
    return records


def build_question_records(meetings: list) -> list:
    """Build a flattened cross-meeting question list with persisted statuses."""
    records = []
    for meeting in meetings:
        _, questions = parse_actions_md(meeting.get("actions_and_questions", ""))
        statuses = get_statuses(meeting.get("_filename", ""))
        try:
            saved_at = datetime.fromisoformat(meeting["saved_at"])
        except Exception:
            saved_at = datetime.now()

        for i, question in enumerate(questions):
            records.append({
                "meeting_name": meeting.get("name", "Untitled Meeting"),
                "meeting_filename": meeting.get("_filename", ""),
                "meeting_saved_at": saved_at,
                "text": question,
                "status": statuses.get("questions", {}).get(str(i), "Open"),
                "question_index": i,
            })
    return records


def build_structured_meeting_context(meetings: list) -> str:
    """Build a structured summary with tracked statuses to ground chat responses."""
    blocks = []
    for meeting in meetings:
        saved_at = datetime.fromisoformat(meeting["saved_at"]).strftime("%d %b %Y %H:%M")
        filename = meeting.get("_filename", "")
        statuses = get_statuses(filename)
        actions, questions = parse_actions_md(meeting.get("actions_and_questions", ""))
        decisions = parse_decisions(meeting.get("decisions_raw", ""))
        try:
            meeting_dt = datetime.fromisoformat(meeting["saved_at"])
        except Exception:
            meeting_dt = datetime.now()

        action_lines = []
        for i, action in enumerate(actions):
            action_text, deadline = split_action_text_and_deadline(action["text"])
            status = statuses.get("actions", {}).get(str(i), "Open")
            due_date = infer_due_date(deadline, meeting_dt)
            due_bits = []
            if deadline:
                due_bits.append(f"stated deadline: {deadline}")
            if due_date:
                due_bits.append(f"inferred due date: {due_date.isoformat()}")
                due_bits.append(f"deadline state: {classify_due_bucket(due_date, status)}")
            due_suffix = f" ({'; '.join(due_bits)})" if due_bits else ""
            action_lines.append(f"- [{status}] [{action['owner']}] {action_text}{due_suffix}")
        if not action_lines:
            action_lines.append("- None")

        decision_lines = []
        for i, decision in enumerate(decisions):
            status = statuses.get("decisions", {}).get(str(i), "Open")
            owner_prefix = f"[{decision['owner']}] " if decision["owner"].upper() != "TEAM" else ""
            decision_lines.append(f"- [{status}] {owner_prefix}{decision['text']}")
        if not decision_lines:
            decision_lines.append("- None")

        question_lines = []
        for i, question in enumerate(questions):
            status = statuses.get("questions", {}).get(str(i), "Open")
            question_lines.append(f"- [{status}] {question}")
        if not question_lines:
            question_lines.append("- None")

        blocks.append(f"""
=== Structured Summary: {meeting['name']} ({saved_at}) ===

ACTIONS:
{chr(10).join(action_lines)}

DECISIONS:
{chr(10).join(decision_lines)}

OPEN QUESTIONS:
{chr(10).join(question_lines)}
""")
    return "\n".join(blocks)


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
    icon = {"waiting": "○", "running": "◉", "done": "●", "skipped": "◌"}[state]
    return f"""
    <div class="agent-card {state}">
      <span class="dot"></span>
      <span><strong>{icon} {label}</strong> — {description}</span>
    </div>"""


def agent_card(label: str, description: str, state: str) -> str:
    state_label = {
        "waiting": "Waiting",
        "running": "Running",
        "done": "Done",
        "skipped": "Skipped",
    }[state]
    return f"""
    <div class="agent-card {state}">
      <div class="agent-card-copy">
        <div class="agent-card-title"><span class="dot"></span>{html.escape(label)}</div>
        <div class="agent-card-description">{html.escape(description)}</div>
      </div>
      <div class="agent-card-state">{state_label}</div>
    </div>"""


def render_action_dashboard(meetings: list):
    """Render a cross-meeting action dashboard with filters and inline status updates."""
    st.markdown("""
    <div class="header-block">
      <h1>📋 Action Dashboard</h1>
      <p>Track action items across all saved meetings and update statuses in one place.</p>
    </div>""", unsafe_allow_html=True)

    if not meetings:
        st.warning("No saved meetings yet. Run the pipeline and save your first one.")
        return

    records = build_action_records(meetings)
    if not records:
        st.info("No actions have been extracted from your saved meetings yet.")
        return

    status_options = ["Open", "In Progress", "Done"]
    owner_options = sorted({r["owner"] for r in records if r["owner"]})
    meeting_options = sorted({r["meeting_name"] for r in records})
    deadline_options = ["All deadlines", "Overdue", "Due soon", "Upcoming", "No deadline"]
    sort_options = [
        "Meeting date (newest)",
        "Meeting date (oldest)",
        "Status",
        "Owner (A-Z)",
        "Action text (A-Z)",
    ]

    filter_statuses = st.multiselect(
        "Filter by status",
        status_options,
        default=status_options,
    )
    col_owner, col_meeting, col_deadline, col_sort, col_search = st.columns([1, 1, 1, 1, 2])
    with col_owner:
        selected_owner = st.selectbox("Owner", ["All owners"] + owner_options)
    with col_meeting:
        selected_meeting = st.selectbox("Meeting", ["All meetings"] + meeting_options)
    with col_deadline:
        selected_deadline = st.selectbox("Deadline", deadline_options, index=0)
    with col_sort:
        selected_sort = st.selectbox("Sort by", sort_options, index=0)
    with col_search:
        search_term = st.text_input("Search", placeholder="Search action text or deadline")

    filtered = []
    search_term_lower = search_term.strip().lower()
    for record in records:
        if filter_statuses and record["status"] not in filter_statuses:
            continue
        if selected_owner != "All owners" and record["owner"] != selected_owner:
            continue
        if selected_meeting != "All meetings" and record["meeting_name"] != selected_meeting:
            continue
        if selected_deadline != "All deadlines" and record["due_bucket"] != selected_deadline:
            continue
        haystack = f"{record['text']} {record['deadline']}".lower()
        if search_term_lower and search_term_lower not in haystack:
            continue
        filtered.append(record)

    status_order = {"Open": 0, "In Progress": 1, "Done": 2}
    if selected_sort == "Meeting date (newest)":
        filtered.sort(key=lambda r: r["meeting_saved_at"], reverse=True)
    elif selected_sort == "Meeting date (oldest)":
        filtered.sort(key=lambda r: r["meeting_saved_at"])
    elif selected_sort == "Status":
        filtered.sort(key=lambda r: (status_order.get(r["status"], 99), -r["meeting_saved_at"].timestamp()))
    elif selected_sort == "Owner (A-Z)":
        filtered.sort(key=lambda r: (r["owner"] == "UNASSIGNED", r["owner"].lower(), -r["meeting_saved_at"].timestamp()))
    elif selected_sort == "Action text (A-Z)":
        filtered.sort(key=lambda r: (r["text"].lower(), -r["meeting_saved_at"].timestamp()))

    open_count = sum(1 for r in records if r["status"] == "Open")
    progress_count = sum(1 for r in records if r["status"] == "In Progress")
    done_count = sum(1 for r in records if r["status"] == "Done")
    overdue_count = sum(1 for r in records if r["due_bucket"] == "Overdue")
    due_soon_count = sum(1 for r in records if r["due_bucket"] == "Due soon")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("All Actions", len(records))
    m2.metric("Open", open_count)
    m3.metric("In Progress", progress_count)
    m4.metric("Done", done_count)
    st.caption(f"{overdue_count} overdue · {due_soon_count} due soon")

    st.markdown(f"**Showing {len(filtered)} of {len(records)} actions**")

    if not filtered:
        st.info("No actions matched the current filters.")
        return

    for record in filtered:
        deadline_suffix = f" _({record['deadline']})_" if record["deadline"] else ""
        owner_badge = (
            f'<span class="action-owner">{record["owner"]}</span>'
            if record["owner"].upper() != "UNASSIGNED" else ""
        )
        due_meta = ""
        if record["due_bucket"] in {"Overdue", "Due soon", "Upcoming"} and record["due_date"]:
            due_meta = f" · {record['due_bucket']} ({record['due_date'].strftime('%d %b %Y')})"
        meta = f"{record['meeting_name']} · {record['meeting_saved_at'].strftime('%d %b %Y %H:%M')}{due_meta}"
        st.caption(meta)
        col_main, col_status = st.columns([5, 1])
        with col_main:
            st.markdown(f"""
            <div class="action-item" style="margin-bottom:0">
              {owner_badge}
              <span>{record['text']}{deadline_suffix}</span>
            </div>""", unsafe_allow_html=True)
        with col_status:
            new_status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(record["status"]),
                key=f"dashboard_action_status_{record['meeting_filename']}_{record['action_index']}",
                label_visibility="collapsed",
            )
            if new_status != record["status"]:
                save_status(record["meeting_filename"], "actions", record["action_index"], new_status)
                st.rerun()


def render_decision_dashboard(meetings: list):
    """Render a cross-meeting decision dashboard with filters and inline status updates."""
    st.markdown("""
    <div class="header-block">
      <h1>🟢 Decisions Dashboard</h1>
      <p>Track decisions across all saved meetings and update their statuses in one place.</p>
    </div>""", unsafe_allow_html=True)

    if not meetings:
        st.warning("No saved meetings yet. Run the pipeline and save your first one.")
        return

    records = build_decision_records(meetings)
    if not records:
        st.info("No decisions have been extracted from your saved meetings yet.")
        return

    status_options = ["Open", "In Progress", "Done"]
    owner_options = sorted({r["owner"] for r in records if r["owner"] and r["owner"] != "TEAM"})
    meeting_options = sorted({r["meeting_name"] for r in records})
    sort_options = [
        "Meeting date (newest)",
        "Meeting date (oldest)",
        "Status",
        "Owner (A-Z)",
        "Decision text (A-Z)",
    ]

    filter_statuses = st.multiselect(
        "Filter by status",
        status_options,
        default=status_options,
        key="decision_dashboard_statuses",
    )
    col_owner, col_meeting, col_sort, col_search = st.columns([1, 1, 1, 2])
    with col_owner:
        selected_owner = st.selectbox("Owner", ["All owners"] + owner_options, key="decision_dashboard_owner")
    with col_meeting:
        selected_meeting = st.selectbox("Meeting", ["All meetings"] + meeting_options, key="decision_dashboard_meeting")
    with col_sort:
        selected_sort = st.selectbox("Sort by", sort_options, index=0, key="decision_dashboard_sort")
    with col_search:
        search_term = st.text_input("Search", placeholder="Search decision text", key="decision_dashboard_search")

    filtered = []
    search_term_lower = search_term.strip().lower()
    for record in records:
        if filter_statuses and record["status"] not in filter_statuses:
            continue
        if selected_owner != "All owners" and record["owner"] != selected_owner:
            continue
        if selected_meeting != "All meetings" and record["meeting_name"] != selected_meeting:
            continue
        if search_term_lower and search_term_lower not in record["text"].lower():
            continue
        filtered.append(record)

    status_order = {"Open": 0, "In Progress": 1, "Done": 2}
    if selected_sort == "Meeting date (newest)":
        filtered.sort(key=lambda r: r["meeting_saved_at"], reverse=True)
    elif selected_sort == "Meeting date (oldest)":
        filtered.sort(key=lambda r: r["meeting_saved_at"])
    elif selected_sort == "Status":
        filtered.sort(key=lambda r: (status_order.get(r["status"], 99), -r["meeting_saved_at"].timestamp()))
    elif selected_sort == "Owner (A-Z)":
        filtered.sort(key=lambda r: (r["owner"] == "TEAM", r["owner"].lower(), -r["meeting_saved_at"].timestamp()))
    elif selected_sort == "Decision text (A-Z)":
        filtered.sort(key=lambda r: (r["text"].lower(), -r["meeting_saved_at"].timestamp()))

    open_count = sum(1 for r in records if r["status"] == "Open")
    progress_count = sum(1 for r in records if r["status"] == "In Progress")
    done_count = sum(1 for r in records if r["status"] == "Done")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("All Decisions", len(records))
    m2.metric("Open", open_count)
    m3.metric("In Progress", progress_count)
    m4.metric("Done", done_count)

    st.markdown(f"**Showing {len(filtered)} of {len(records)} decisions**")

    if not filtered:
        st.info("No decisions matched the current filters.")
        return

    for record in filtered:
        owner_badge = (
            f'<span class="decision-owner">{record["owner"]}</span>'
            if record["owner"].upper() != "TEAM" else ""
        )
        meta = f"{record['meeting_name']} · {record['meeting_saved_at'].strftime('%d %b %Y %H:%M')}"
        st.caption(meta)
        col_main, col_status = st.columns([5, 1])
        with col_main:
            st.markdown(f"""
            <div class="decision-item" style="margin-bottom:0">
              {owner_badge}
              <span>{record['text']}</span>
            </div>""", unsafe_allow_html=True)
        with col_status:
            new_status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(record["status"]),
                key=f"dashboard_decision_status_{record['meeting_filename']}_{record['decision_index']}",
                label_visibility="collapsed",
            )
            if new_status != record["status"]:
                save_status(record["meeting_filename"], "decisions", record["decision_index"], new_status)
                st.rerun()


def render_question_dashboard(meetings: list):
    """Render a cross-meeting question dashboard with filters and inline status updates."""
    st.markdown("""
    <div class="header-block">
      <h1>❓ Questions Dashboard</h1>
      <p>Track open questions across all saved meetings and update their statuses in one place.</p>
    </div>""", unsafe_allow_html=True)

    if not meetings:
        st.warning("No saved meetings yet. Run the pipeline and save your first one.")
        return

    records = build_question_records(meetings)
    if not records:
        st.info("No open questions have been extracted from your saved meetings yet.")
        return

    status_options = ["Open", "In Progress", "Done"]
    meeting_options = sorted({r["meeting_name"] for r in records})
    sort_options = [
        "Meeting date (newest)",
        "Meeting date (oldest)",
        "Status",
        "Question text (A-Z)",
    ]

    filter_statuses = st.multiselect(
        "Filter by status",
        status_options,
        default=status_options,
        key="question_dashboard_statuses",
    )
    col_meeting, col_sort, col_search = st.columns([1, 1, 2])
    with col_meeting:
        selected_meeting = st.selectbox("Meeting", ["All meetings"] + meeting_options, key="question_dashboard_meeting")
    with col_sort:
        selected_sort = st.selectbox("Sort by", sort_options, index=0, key="question_dashboard_sort")
    with col_search:
        search_term = st.text_input("Search", placeholder="Search question text", key="question_dashboard_search")

    filtered = []
    search_term_lower = search_term.strip().lower()
    for record in records:
        if filter_statuses and record["status"] not in filter_statuses:
            continue
        if selected_meeting != "All meetings" and record["meeting_name"] != selected_meeting:
            continue
        if search_term_lower and search_term_lower not in record["text"].lower():
            continue
        filtered.append(record)

    status_order = {"Open": 0, "In Progress": 1, "Done": 2}
    if selected_sort == "Meeting date (newest)":
        filtered.sort(key=lambda r: r["meeting_saved_at"], reverse=True)
    elif selected_sort == "Meeting date (oldest)":
        filtered.sort(key=lambda r: r["meeting_saved_at"])
    elif selected_sort == "Status":
        filtered.sort(key=lambda r: (status_order.get(r["status"], 99), -r["meeting_saved_at"].timestamp()))
    elif selected_sort == "Question text (A-Z)":
        filtered.sort(key=lambda r: (r["text"].lower(), -r["meeting_saved_at"].timestamp()))

    open_count = sum(1 for r in records if r["status"] == "Open")
    progress_count = sum(1 for r in records if r["status"] == "In Progress")
    done_count = sum(1 for r in records if r["status"] == "Done")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("All Questions", len(records))
    m2.metric("Open", open_count)
    m3.metric("In Progress", progress_count)
    m4.metric("Done", done_count)

    st.markdown(f"**Showing {len(filtered)} of {len(records)} questions**")

    if not filtered:
        st.info("No questions matched the current filters.")
        return

    for record in filtered:
        meta = f"{record['meeting_name']} · {record['meeting_saved_at'].strftime('%d %b %Y %H:%M')}"
        st.caption(meta)
        col_main, col_status = st.columns([5, 1])
        with col_main:
            st.markdown(f"""
            <div class="question-item" style="margin-bottom:0">
              <span>{record['text']}</span>
            </div>""", unsafe_allow_html=True)
        with col_status:
            new_status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(record["status"]),
                key=f"dashboard_question_status_{record['meeting_filename']}_{record['question_index']}",
                label_visibility="collapsed",
            )
            if new_status != record["status"]:
                save_status(record["meeting_filename"], "questions", record["question_index"], new_status)
                st.rerun()


def format_dashboard_record(record: dict, kind: str) -> str:
    """Format a deterministic chat record line with meeting context."""
    meeting = record["meeting_name"]
    status = record["status"]
    if kind == "action":
        owner = record["owner"]
        deadline = f" ({record['deadline']})" if record.get("deadline") else ""
        return f"- [{status}] {owner}: {record['text']}{deadline} — {meeting}"
    if kind == "decision":
        owner_prefix = f"{record['owner']}: " if record.get("owner") and record["owner"] != "TEAM" else ""
        return f"- [{status}] {owner_prefix}{record['text']} — {meeting}"
    return f"- [{status}] {record['text']} — {meeting}"


def deterministic_chat_response(query: str, meetings: list) -> str | None:
    """Answer status/count/deadline queries directly from saved structured data when possible."""
    q = re.sub(r"\s+", " ", query.lower()).strip()
    actions = build_action_records(meetings)
    decisions = build_decision_records(meetings)
    questions = build_question_records(meetings)
    count_query = any(token in q for token in ["how many", "count", "number of"])

    def list_or_count(records, kind: str, noun: str, heading: str):
        if count_query:
            count = len(records)
            verb = "is" if count == 1 else "are"
            return f"There {verb} {count} {noun}."
        if not records:
            return f"No {noun} found."
        lines = [heading] + [format_dashboard_record(r, kind) for r in records]
        return "\n".join(lines)

    if "overdue" in q:
        overdue = [r for r in actions if r["due_bucket"] == "Overdue"]
        return list_or_count(overdue, "action", "overdue actions", "**Overdue Actions**")

    if "due soon" in q or "due this week" in q:
        due_soon = [r for r in actions if r["due_bucket"] == "Due soon"]
        return list_or_count(due_soon, "action", "actions due soon", "**Due Soon Actions**")

    if "unassigned" in q and ("action" in q or "actions" in q):
        unassigned = [r for r in actions if r["owner"] == "UNASSIGNED"]
        return list_or_count(unassigned, "action", "unassigned actions", "**Unassigned Actions**")

    status_map = {
        "in progress": "In Progress",
        "open": "Open",
        "done": "Done",
    }
    requested_status = next((value for key, value in status_map.items() if key in q), None)
    asks_actions = "action" in q
    asks_decisions = "decision" in q
    asks_questions = "question" in q

    if requested_status and asks_actions:
        matched = [r for r in actions if r["status"] == requested_status]
        return list_or_count(matched, "action", f"actions marked {requested_status}", f"**Actions Marked {requested_status}**")

    if requested_status and asks_decisions:
        matched = [r for r in decisions if r["status"] == requested_status]
        return list_or_count(matched, "decision", f"decisions marked {requested_status}", f"**Decisions Marked {requested_status}**")

    if requested_status and asks_questions:
        matched = [r for r in questions if r["status"] == requested_status]
        return list_or_count(matched, "question", f"questions marked {requested_status}", f"**Questions Marked {requested_status}**")

    if requested_status and not (asks_actions or asks_decisions or asks_questions):
        action_matches = [r for r in actions if r["status"] == requested_status]
        decision_matches = [r for r in decisions if r["status"] == requested_status]
        question_matches = [r for r in questions if r["status"] == requested_status]
        if count_query:
            return (
                f"There are {len(action_matches)} actions, "
                f"{len(decision_matches)} decisions, and "
                f"{len(question_matches)} questions marked {requested_status}."
            )
        sections = []
        if action_matches:
            sections.append("**Actions**")
            sections.extend(format_dashboard_record(r, "action") for r in action_matches)
        if decision_matches:
            sections.append("**Decisions**")
            sections.extend(format_dashboard_record(r, "decision") for r in decision_matches)
        if question_matches:
            sections.append("**Questions**")
            sections.extend(format_dashboard_record(r, "question") for r in question_matches)
        if sections:
            return "\n".join(sections)
        return f"No tracked items are marked {requested_status}."

    return None


def render_results(actions_and_questions: str, diagram_raw: str,
                   clean_text: str, decisions_raw: str = "",
                   meeting_filename: str = ""):
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
        statuses = get_statuses(meeting_filename)
        if actions:
            for i, a in enumerate(actions):
                current_status = statuses.get("actions", {}).get(str(i), "Open")
                col_main, col_status = st.columns([5, 1])
                with col_main:
                    owner_badge = f'<span class="action-owner">{a["owner"]}</span>' if a["owner"].upper() != "UNASSIGNED" else ""
                    st.markdown(f"""
                    <div class="action-item" style="margin-bottom:0">
                      {owner_badge}
                      <span>{a['text']}</span>
                    </div>""", unsafe_allow_html=True)
                with col_status:
                    new_status = st.selectbox(
                        "Status",
                        ["Open", "In Progress", "Done"],
                        index=["Open", "In Progress", "Done"].index(current_status),
                        key=f"action_status_{meeting_filename}_{i}",
                        label_visibility="collapsed",
                    )
                    if new_status != current_status:
                        save_status(meeting_filename, "actions", i, new_status)
                        st.rerun()
        else:
            st.info("No action items were identified in this meeting.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button("⬇️ Download Actions (.md)", data=actions_and_questions,
            file_name=f"actions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown")

    with tab_decisions:
        statuses = get_statuses(meeting_filename)
        if decisions:
            for i, d in enumerate(decisions):
                current_status = statuses.get("decisions", {}).get(str(i), "Open")
                col_main, col_status = st.columns([5, 1])
                with col_main:
                    owner_badge = f'<span class="decision-owner">{d["owner"]}</span>' if d["owner"].upper() != "TEAM" else ""
                    st.markdown(f"""
                    <div class="decision-item">
                      {owner_badge}
                      <span>{d['text']}</span>
                    </div>""", unsafe_allow_html=True)
                with col_status:
                    new_status = st.selectbox(
                        "Status",
                        ["Open", "In Progress", "Done"],
                        index=["Open", "In Progress", "Done"].index(current_status),
                        key=f"decision_status_{meeting_filename}_{i}",
                        label_visibility="collapsed",
                    )
                    if new_status != current_status:
                        save_status(meeting_filename, "decisions", i, new_status)
                        st.rerun()
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
        statuses = get_statuses(meeting_filename)
        if questions:
            for i, q in enumerate(questions):
                current_status = statuses.get("questions", {}).get(str(i), "Open")
                col_main, col_status = st.columns([5, 1])
                with col_main:
                    st.markdown(f'<div class="question-item">{q}</div>',
                                unsafe_allow_html=True)
                with col_status:
                    new_status = st.selectbox(
                        "Status",
                        ["Open", "In Progress", "Done"],
                        index=["Open", "In Progress", "Done"].index(current_status),
                        key=f"question_status_{meeting_filename}_{i}",
                        label_visibility="collapsed",
                    )
                    if new_status != current_status:
                        save_status(meeting_filename, "questions", i, new_status)
                        st.rerun()
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
if "action_dashboard_mode" not in st.session_state:
    st.session_state.action_dashboard_mode = False
if "decision_dashboard_mode" not in st.session_state:
    st.session_state.decision_dashboard_mode = False
if "question_dashboard_mode" not in st.session_state:
    st.session_state.question_dashboard_mode = False
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
        st.session_state.action_dashboard_mode = False
        st.session_state.decision_dashboard_mode = False
        st.session_state.question_dashboard_mode = False
        st.rerun()

    if st.button("📋 Action Dashboard", use_container_width=True):
        st.session_state.action_dashboard_mode = True
        st.session_state.decision_dashboard_mode = False
        st.session_state.question_dashboard_mode = False
        st.session_state.chat_mode = False
        st.session_state.hld_mode = False
        st.session_state.loaded_meeting = None
        st.session_state.pipeline_result = None
        st.rerun()

    if st.button("🟢 Decisions Dashboard", use_container_width=True):
        st.session_state.decision_dashboard_mode = True
        st.session_state.action_dashboard_mode = False
        st.session_state.question_dashboard_mode = False
        st.session_state.chat_mode = False
        st.session_state.hld_mode = False
        st.session_state.loaded_meeting = None
        st.session_state.pipeline_result = None
        st.rerun()

    if st.button("❓ Questions Dashboard", use_container_width=True):
        st.session_state.question_dashboard_mode = True
        st.session_state.action_dashboard_mode = False
        st.session_state.decision_dashboard_mode = False
        st.session_state.chat_mode = False
        st.session_state.hld_mode = False
        st.session_state.loaded_meeting = None
        st.session_state.pipeline_result = None
        st.rerun()

    if st.button("📄 Generate Project HLD", use_container_width=True):
        st.session_state.hld_mode = True
        st.session_state.action_dashboard_mode = False
        st.session_state.decision_dashboard_mode = False
        st.session_state.question_dashboard_mode = False
        st.session_state.chat_mode = False
        st.session_state.loaded_meeting = None
        st.session_state.pipeline_result = None
        st.session_state.hld_bytes = None
        st.rerun()

    if st.button("💬 Ask about your meetings", use_container_width=True):
        st.session_state.chat_mode = True
        st.session_state.action_dashboard_mode = False
        st.session_state.decision_dashboard_mode = False
        st.session_state.question_dashboard_mode = False
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
                        st.session_state.action_dashboard_mode = False
                        st.session_state.decision_dashboard_mode = False
                        st.session_state.question_dashboard_mode = False
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

# Case 0: Action dashboard
if st.session_state.action_dashboard_mode:
    meetings = load_all_meetings()
    render_action_dashboard(meetings)

# Case 1: Decisions dashboard
elif st.session_state.decision_dashboard_mode:
    meetings = load_all_meetings()
    render_decision_dashboard(meetings)

# Case 2: Questions dashboard
elif st.session_state.question_dashboard_mode:
    meetings = load_all_meetings()
    render_question_dashboard(meetings)

# Case 3: Chat with your meetings
elif st.session_state.chat_mode:
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
            raw_blocks = []
            for m in meetings:
                saved_at = datetime.fromisoformat(m["saved_at"]).strftime("%d %b %Y %H:%M")
                raw_blocks.append(f"""
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
            structured = build_structured_meeting_context(meetings)
            raw = "\n".join(raw_blocks)
            return f"""## Structured Status Summary
{structured}

## Full Meeting Content
{raw}"""

        CHAT_SYSTEM_PROMPT = """You are an expert assistant with full knowledge of the meeting notes, 
decisions, actions, and architecture discussions from the user's saved meetings.

Answer questions clearly and concisely, referencing specific meetings by name where relevant.
Format responses in plain prose where possible. Use bullet points sparingly.
Avoid large headings — use bold text instead for emphasis.
When listing items like actions or decisions, format them clearly.
For questions about progress, status, what is open, what is in progress, or what is done, use the structured status summary as the source of truth.
For action deadline questions, use the inferred due dates and deadline states from the structured summary when available, but make clear they are inferred from the saved meeting text.
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
                    user_query = st.session_state.chat_history[-1]["content"]
                    deterministic_reply = deterministic_chat_response(user_query, meetings)
                    if deterministic_reply is not None:
                        st.session_state.chat_history.append({
                            "role": "assistant", "content": deterministic_reply
                        })
                        st.rerun()

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

# Case 4: HLD mode
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

# Case 5: Viewing a saved meeting
elif st.session_state.loaded_meeting:
    m = st.session_state.loaded_meeting
    saved_at = datetime.fromisoformat(m["saved_at"]).strftime("%d %b %Y at %H:%M")
    redaction_suffix = " · Sensitive text tokenized" if m.get("redaction", {}).get("mode") == "tokenize" else ""
    st.markdown(f"""
    <div class="header-block">
      <h1>📋 {m['name']}</h1>
      <p>Saved {saved_at} · {m.get('source_file', 'unknown source')}{redaction_suffix}</p>
    </div>""", unsafe_allow_html=True)
    render_redaction_notice(m.get("redaction"))
    render_results(
        m["actions_and_questions"],
        m["diagram_raw"],
        m["clean_text"],
        m.get("decisions_raw", ""),  # backwards compatible with older saved meetings
        meeting_filename=m.get("_filename", ""),
    )

# Case 6: Fresh pipeline result
elif st.session_state.pipeline_result:
    r = st.session_state.pipeline_result
    redaction_suffix = " · Sensitive text tokenized" if r.get("redaction", {}).get("mode") == "tokenize" else ""
    st.markdown(f"""
    <div class="header-block">
      <h1>🏛️ Meeting Artefact Pipeline</h1>
      <p>Pipeline complete — save this meeting or review below{redaction_suffix}</p>
    </div>""", unsafe_allow_html=True)
    render_redaction_notice(r.get("redaction"))

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
                        redaction=r.get("redaction"),
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
        meeting_filename="",
    )

# Case 7: Upload screen
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
        privacy_mode_label = st.selectbox(
            "Privacy mode",
            ["Off", "Tokenize sensitive text"],
            index=0,
            help="When enabled, likely sensitive text is tokenized before it reaches OpenAI or saved meeting history.",
        )
        custom_terms_input = st.text_area(
            "Additional sensitive terms (optional)",
            value=os.getenv("REDACTION_TERMS", ""),
            height=90,
            placeholder="Customer names, project codenames, internal systems...",
            help="Comma or newline separated terms to replace with stable placeholders like [TERM_1].",
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
        st.caption("Privacy mode tokenizes likely people, company, email, phone, URL, IP, and custom sensitive terms before analysis.")

    if uploaded_file:
        suffix = Path(uploaded_file.name).suffix.lower()
        is_audio = suffix in [".m4a", ".mp3", ".wav"]
        source_type = "audio" if is_audio else ("notes" if suffix == ".md" else "transcript")
        redaction_mode = "tokenize" if privacy_mode_label == "Tokenize sensitive text" else "off"
        custom_redactions = parse_sensitive_terms(custom_terms_input)

        with col_upload:
            _, btn_col = st.columns([5, 1])
            with btn_col:
                run = st.button("⚡ Run Pipeline", type="primary", use_container_width=True)

        if run:
            st.markdown("---")
            progress_placeholder = st.empty()
            st.session_state.agent_states = {
                "ingestion": "waiting",
                "redaction": "waiting" if redaction_mode == "tokenize" else "skipped",
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
                            + agent_card("Redaction Agent", "Tokenising sensitive text",      st.session_state.agent_states["redaction"])
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

                redaction_summary = {"mode": "off", "counts": {}, "custom_term_count": len(custom_redactions)}
                if redaction_mode == "tokenize":
                    st.session_state.agent_states["redaction"] = "running"; render_progress()
                    raw_input, redaction_summary = tokenize_sensitive_text(raw_input, custom_redactions)
                    st.session_state.agent_states["redaction"] = "done"; render_progress()

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
                    "redaction": redaction_summary,
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
