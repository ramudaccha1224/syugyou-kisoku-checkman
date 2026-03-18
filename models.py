"""Pydanticモデル定義"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


# --- チェックリスト関連 ---

class Category(str, Enum):
    ABSOLUTE = "ABSOLUTE"
    RELATIVE = "RELATIVE"
    IMPORTANT_ARBITRARY = "IMPORTANT_ARBITRARY"
    VOLUNTARY = "VOLUNTARY"


class TriggerLogic(str, Enum):
    ALWAYS = "always"
    ON_USER_YES_OR_UNKNOWN = "on_user_yes_or_unknown"
    STRONGLY_RECOMMENDED = "strongly_recommended"
    OPTIONAL = "optional"


class ChecklistItem(BaseModel):
    id: str
    category: Category
    item_name: str
    hearing_question: Optional[str] = None
    trigger_logic: TriggerLogic
    search_hints: list[str]


class Checklist(BaseModel):
    description: str
    categories: dict[str, str]
    items: list[ChecklistItem]


# --- 知識ベース関連 ---

class KnowledgeEntry(BaseModel):
    item_id: str
    subject: str
    legal_basis: str
    evaluation_criteria: str
    if_unknown_guidance: str
    suggested_title: str
    model_clause: str


class KnowledgeBase(BaseModel):
    description: str
    knowledge_entries: list[KnowledgeEntry]


# --- ヒアリング関連 ---

class AnswerChoice(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class HearingAnswer(BaseModel):
    item_id: str
    item_name: str
    answer: AnswerChoice


class HearingResult(BaseModel):
    answers: list[HearingAnswer]
