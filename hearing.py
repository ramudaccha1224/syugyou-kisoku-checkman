"""Step1: ヒアリング（問診）ロジック"""

from __future__ import annotations

from models import (
    AnswerChoice,
    ChecklistItem,
    Checklist,
    HearingAnswer,
    HearingResult,
    TriggerLogic,
)


def get_hearing_items(checklist: Checklist) -> list[ChecklistItem]:
    """ヒアリングが必要な項目を抽出する。

    trigger_logic が 'always' の項目（絶対的必要記載事項）はヒアリング不要。
    hearing_question が None の項目もスキップ。
    """
    return [
        item
        for item in checklist.items
        if item.trigger_logic != TriggerLogic.ALWAYS and item.hearing_question
    ]


def build_hearing_result(
    hearing_items: list[ChecklistItem],
    raw_answers: dict[str, str],
) -> HearingResult:
    """UIから受け取った生の回答を HearingResult に変換する。

    Args:
        hearing_items: ヒアリング対象の ChecklistItem リスト
        raw_answers: {item_id: "定めている"|"定めていない"|"分からない"}

    Returns:
        HearingResult
    """
    answer_map = {
        "定めている": AnswerChoice.YES,
        "定めていない": AnswerChoice.NO,
        "分からない": AnswerChoice.UNKNOWN,
    }

    answers = []
    for item in hearing_items:
        raw = raw_answers.get(item.id, "分からない")
        answers.append(
            HearingAnswer(
                item_id=item.id,
                item_name=item.item_name,
                answer=answer_map.get(raw, AnswerChoice.UNKNOWN),
            )
        )

    return HearingResult(answers=answers)
