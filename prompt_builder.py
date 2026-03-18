"""Step2: システムプロンプトの動的生成"""

from __future__ import annotations

from models import (
    AnswerChoice,
    Category,
    Checklist,
    ChecklistItem,
    HearingResult,
    KnowledgeEntry,
    KnowledgeBase,
    TriggerLogic,
)


def build_system_prompt(
    checklist: Checklist,
    knowledge: KnowledgeBase,
    hearing_result: HearingResult,
) -> str:
    """ヒアリング結果・チェックリスト・知識ベースからシステムプロンプトを動的生成する。"""

    # ヒアリング回答をitem_idでルックアップ
    answer_map: dict[str, AnswerChoice] = {
        a.item_id: a.answer for a in hearing_result.answers
    }

    # 知識ベースをitem_idでルックアップ
    knowledge_map: dict[str, KnowledgeEntry] = {
        e.item_id: e for e in knowledge.knowledge_entries
    }

    # --- 各カテゴリのチェック項目を分類 ---
    critical_items: list[str] = []  # 絶対的必要記載事項
    high_items: list[str] = []      # 相対的（制度あり → 法的義務）
    explore_items: list[str] = []   # 「分からない」→ 探索指示
    recommended_items: list[str] = []  # 重要任意
    optional_items: list[str] = []  # 任意

    for item in checklist.items:
        kb = knowledge_map.get(item.id)
        section = _format_item_section(item, kb)

        if item.category == Category.ABSOLUTE:
            critical_items.append(section)

        elif item.category == Category.RELATIVE:
            user_answer = answer_map.get(item.id)
            if user_answer == AnswerChoice.YES:
                high_items.append(section)
            elif user_answer == AnswerChoice.UNKNOWN:
                explore_items.append(
                    _format_explore_section(item, kb)
                )
            # NO → スキップ（制度なし）

        elif item.category == Category.IMPORTANT_ARBITRARY:
            user_answer = answer_map.get(item.id)
            if user_answer == AnswerChoice.NO:
                continue  # 明示的に不要
            recommended_items.append(section)

        elif item.category == Category.VOLUNTARY:
            user_answer = answer_map.get(item.id)
            if user_answer == AnswerChoice.NO:
                continue
            optional_items.append(section)

    # --- プロンプト組み立て ---
    prompt_parts = [
        _ROLE_SECTION,
        _METHODOLOGY_SECTION,
    ]

    if critical_items:
        prompt_parts.append(
            "## 絶対的必要記載事項（労基法上、全ての就業規則に記載が義務づけられている項目）\n"
            "以下の項目が就業規則に記載されているか、内容（意味）ベースで厳格に確認せよ。\n"
            "条番号ではなく、記載内容でマッチングすること。欠落があれば指摘せよ。\n\n"
            + "\n---\n".join(critical_items)
        )

    if high_items:
        prompt_parts.append(
            "## 相対的必要記載事項（ヒアリングにより制度の存在が確認された項目＝記載義務あり）\n"
            "ヒアリングの結果、ユーザーは以下の制度を「定めている」と回答した。\n"
            "制度が存在する以上、法的記載義務がある。未記載であれば法違反として指摘せよ。\n\n"
            + "\n---\n".join(high_items)
        )

    if explore_items:
        prompt_parts.append(
            "## 相対的必要記載事項（ユーザーが「分からない」と回答した項目＝要探索）\n"
            "以下の項目についてユーザーは「分からない」と回答した。\n"
            "就業規則のテキスト内に search_hints のキーワードが含まれるかを能動的に探索し、\n"
            "- 見つかった場合: 「実態として規定あり」とみなし、法的妥当性をチェックせよ。\n"
            "- 見つからなかった場合: 「制度として運用しているなら、記載しないと法違反（またはリスクあり）です」と警告し、モデル条文を提示せよ。\n\n"
            + "\n---\n".join(explore_items)
        )

    if recommended_items:
        prompt_parts.append(
            "## 特に重要な任意記載事項\n"
            "法的義務ではないが、企業防衛・トラブル回避の観点から記載が強く推奨される項目。\n"
            "未記載の場合はリスクを説明し、モデル条文を提案せよ。\n\n"
            + "\n---\n".join(recommended_items)
        )

    if optional_items:
        prompt_parts.append(
            "## その他の任意記載事項\n"
            "組織の透明性向上に資する項目。未記載でも法的問題はないが、簡潔に提案すること。\n\n"
            + "\n---\n".join(optional_items)
        )

    prompt_parts.append(_OUTPUT_FORMAT_SECTION)

    return "\n\n".join(prompt_parts)


def _format_item_section(item: ChecklistItem, kb: KnowledgeEntry | None) -> str:
    """個別チェック項目のプロンプトセクションを生成"""
    lines = [
        f"### [{item.id}] {item.item_name}",
        f"- 検索キーワード: {', '.join(item.search_hints)}",
    ]
    if kb:
        lines.extend([
            f"- 根拠法: {kb.legal_basis}",
            f"- 判定基準: {kb.evaluation_criteria}",
            f"- 補足ガイダンス: {kb.if_unknown_guidance}",
            f"- 推奨条文タイトル: {kb.suggested_title}",
            f"- モデル条文:\n```\n{kb.model_clause}\n```",
        ])
    return "\n".join(lines)


def _format_explore_section(item: ChecklistItem, kb: KnowledgeEntry | None) -> str:
    """「分からない」項目の探索指示セクション"""
    lines = [
        f"### [{item.id}] {item.item_name}（要探索）",
        f"- 検索キーワード: {', '.join(item.search_hints)}",
    ]
    if kb:
        lines.extend([
            f"- 根拠法: {kb.legal_basis}",
            f"- 判定基準: {kb.evaluation_criteria}",
            f"- 探索・回答戦略: {kb.if_unknown_guidance}",
            f"- 推奨条文タイトル: {kb.suggested_title}",
            f"- モデル条文:\n```\n{kb.model_clause}\n```",
        ])
    return "\n".join(lines)


# --- 固定プロンプトセクション ---

_ROLE_SECTION = """\
# あなたの役割
あなたは日本の労働法に精通した社会保険労務士（社労士）AIアシスタントです。
ユーザーが提出した「就業規則」のテキストを精査し、法的不備・リスク・改善点を体系的に指摘してください。

## 基本姿勢
- 専門家として正確かつ具体的に指摘すること。
- 法令の根拠条文を明示すること。
- 不備に対しては、厚生労働省モデル就業規則に準拠した改善案（モデル条文）を提示すること。
- 良好に整備されている点も簡潔に評価すること。"""

_METHODOLOGY_SECTION = """\
# 解析手法

## 条番号への依存排除
- 就業規則の既存の条番号は無視し、内容（意味）でマッピングせよ。
- 回答時は、既存の条文があればその条番号を維持し、新規提案時は「第○条」とプレースホルダを使用せよ。

## 別規程への委任・個別通知書の取扱い（重要な法的原則）
就業規則の実務において、以下は完全に適法かつ一般的な手法であることを必ず理解した上でチェックせよ。
これらを知らずに「本体に記載がない＝不備」と判定することは誤りである。

1. **別規程への委任は適法**:
   - 就業規則本体に「賃金については別に定める賃金規程による」「退職金は退職金規程による」等の委任条項がある場合、
     その事項の詳細は別規程で定めることが労働基準法上認められている。
   - この場合、就業規則本体には委任条項があれば足り、詳細な計算式や手当の内訳が本体になくても法違反ではない。
   - チェック時は「別規程に委任している旨の記載があるか」を確認し、あれば「適切に委任されている」と判定すること。
     ただし「別規程の内容も併せて確認することを推奨します」と助言を添えること。

2. **パートタイム・有期契約社員等の労働条件**:
   - パートタイム労働者や有期契約社員について、就業規則の本則と異なる労働条件を個別の労働条件通知書や
     個別の雇用契約書で定めることは適法である（労働基準法第15条、パートタイム・有期雇用労働法）。
   - 就業規則に「パートタイム労働者の労働条件については個別の労働条件通知書による」旨の記載がある場合は適切。
   - 就業規則の適用範囲を「正社員に適用する」と限定し、パート等に別規則を設けることも一般的な実務慣行である。

3. **「別に定める」の評価基準**:
   - 「別に定める」と記載されている場合 → 委任先の規程が存在する前提で、法的には**適切**と判定する。
   - 委任先の規程が提出されていない場合 → 「不備」ではなく「別規程の確認を推奨」と助言する。
   - 何も言及がない場合 → はじめて「記載不備」として指摘する。

## 判定の考え方
- **絶対的必要記載事項**および**相対的必要記載事項（制度ありと判明したもの）**は、いずれも法的記載義務がある。両者の重要度に差はない。
- **特に重要な任意記載事項**: 法的義務ではないが、企業防衛・トラブル回避の観点から記載が強く推奨される。
- **その他の任意記載事項**: 未記載でも法的問題なし。軽い提案のみ。

## 各項目の判定ラベル（出力で使用するラベル）
各チェック項目の判定には、以下の3種類のみを使用せよ。「CRITICAL」「HIGH」等の英語ラベルは使用禁止。
- **不備**: 記載がない、または法的に不十分な内容が確認された場合
- **要確認**: 別規程への委任がある、内容は存在するが一部不明瞭、または追記が望ましい場合
- **適切**: 法的に十分な記載がある場合"""

_OUTPUT_FORMAT_SECTION = """\
# 出力フォーマット
以下の構成で、Markdown形式で出力せよ。
「CRITICAL」「HIGH」「RECOMMENDED」等の英語の専門用語は一切使用しないこと。

## 1. 総合評価サマリー
カテゴリ別に「不備」と「要確認」の件数と該当項目の概要を一覧で示す。
以下のフォーマットを厳格に守ること:

```
● 絶対的必要記載事項：不備 ○箇所（該当項目の概要）　要確認 ○箇所（該当項目の概要）
● 相対的必要記載事項：不備 ○箇所（該当項目の概要）　要確認 ○箇所（該当項目の概要）
● 特に重要な任意記載事項：不備 ○箇所（該当項目の概要）　要確認 ○箇所（該当項目の概要）
```

- 不備・要確認が0箇所の場合は「なし」と記載。
- 括弧内には「労働時間に関する定め」「賃金に関する定め」等、ユーザーが一目で何の項目か分かる概要を記載。

## 2. 詳細チェック結果
判定が「不備」または「要確認」の項目のみを出力せよ。「適切」と判定した項目は詳細に含めないこと。
各項目ごとに以下の形式で出力:

### 項目名
- **判定**: 不備 / 要確認
- **現状**: 就業規則内の該当箇所の要約（条番号があればそれを記載）
- **指摘事項**: 具体的な問題点
- **根拠法**: 関連する法令
- **改善案**: モデル条文に基づく具体的な修正・追加案

## 3. 優先対応リスト
「不備」の項目 → 「要確認」の項目 の順に、対応すべき項目を優先度順にリスト化。

## 4. 総括コメント
全体を通じた法的アドバイスや、特に注意すべきポイントのまとめ。"""
