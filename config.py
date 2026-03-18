"""設定・定数管理"""

from __future__ import annotations

import json
from pathlib import Path

import os

from models import Checklist, KnowledgeBase

# .env がある場合（ローカル開発時）は読み込む
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- 定数 ---
# Streamlit Community Cloud では st.secrets から取得、
# ローカルでは .env / 環境変数から取得
def _get_api_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")

GEMINI_API_KEY: str = _get_api_key()
GEMINI_MODEL: str = "gemini-2.5-flash"

BASE_DIR = Path(__file__).resolve().parent
CHECKLIST_PATH = BASE_DIR / "checklist.json"
KNOWLEDGE_PATH = BASE_DIR / "knowledge.json"


def load_checklist() -> Checklist:
    """checklist.json を読み込んで Pydantic モデルに変換"""
    with open(CHECKLIST_PATH, encoding="utf-8") as f:
        return Checklist.model_validate(json.load(f))


def load_knowledge() -> KnowledgeBase:
    """knowledge.json を読み込んで Pydantic モデルに変換"""
    with open(KNOWLEDGE_PATH, encoding="utf-8") as f:
        return KnowledgeBase.model_validate(json.load(f))
