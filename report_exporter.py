"""チェック結果をGenspark向けレポート指示書として出力する"""

from __future__ import annotations

from datetime import datetime

from models import HearingResult, AnswerChoice


def build_report_markdown(
    check_result: str,
    uploaded_filenames: list[str],
    hearing_result: HearingResult | None,
    supplement_skipped: bool = False,
) -> str:
    """Genspark向けレポート指示書（Markdown）を生成する。

    構成:
      1. Genspark向けレポート作成指示（プロンプト）
      2. チェック概要（メタデータ）
      3. チェック結果本体
    """
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    parts: list[str] = []

    # ==============================
    # セクション1: Genspark向け指示文
    # ==============================
    parts.append(_GENSPARK_INSTRUCTION)

    # ==============================
    # セクション2: チェック概要
    # ==============================
    meta_lines = [
        "---",
        "",
        "# チェック概要",
        "",
        f"- **チェック実施日時**: {now}",
        f"- **チェックツール**: 就業規則チェックマン（Gemini LLM による自動リーガルチェック）",
        "",
        "## 対象ファイル",
    ]
    for fname in uploaded_filenames:
        meta_lines.append(f"- {fname}")

    if supplement_skipped:
        meta_lines.append("")
        meta_lines.append(
            "※ 就業規則内に別規程への参照がありましたが、別規程の追加提出はスキップされました。"
            "別規程が存在する場合は、その内容も併せて確認することを推奨します。"
        )

    # ヒアリング回答サマリー
    if hearing_result and hearing_result.answers:
        meta_lines.append("")
        meta_lines.append("## ヒアリング回答サマリー")
        meta_lines.append("")
        meta_lines.append("| 項目 | 回答 |")
        meta_lines.append("|------|------|")
        for a in hearing_result.answers:
            label = {
                AnswerChoice.YES: "定めている",
                AnswerChoice.NO: "定めていない",
                AnswerChoice.UNKNOWN: "分からない",
            }.get(a.answer, "")
            meta_lines.append(f"| {a.item_name} | {label} |")

    parts.append("\n".join(meta_lines))

    # ==============================
    # セクション3: チェック結果本体
    # ==============================
    parts.append(
        "---\n\n"
        "# リーガルチェック結果\n\n"
        "以下がAIによるリーガルチェックの全結果です。\n\n"
        + check_result
    )

    # ==============================
    # フッター
    # ==============================
    parts.append(
        "\n---\n"
        f"*本資料は「就業規則チェックマン」により {now} に自動生成されました。*\n"
        "*法的助言を構成するものではなく、最終的な判断は社会保険労務士等の専門家にご相談ください。*"
    )

    return "\n\n".join(parts)


# ==============================
# Genspark向け指示テンプレート
# ==============================
_GENSPARK_INSTRUCTION = """\
# レポート作成指示

以下の「チェック概要」と「リーガルチェック結果」をもとに、
就業規則のリーガルチェックレポートを作成してください。

## レポートの構成

1. **エグゼクティブサマリー**（経営者・事業主向け）
   - 専門用語を避け、平易な日本語で記載
   - 「何が問題で」「どうすればいいか」を端的に伝える
   - 対応の優先度が一目で分かるようにする

2. **詳細チェック結果**（社労士・法務担当向け）
   - 根拠法・条文番号を明記
   - 現状の記載内容と、あるべき記載内容の差分を具体的に示す
   - 改善案にはモデル条文を含める

3. **優先対応ロードマップ**
   - 「不備」の項目を最優先、「要確認」の項目を次点として
   - 具体的な対応手順と推奨スケジュールを提案

4. **参考情報**
   - 関連する法令のリスト
   - 厚生労働省モデル就業規則への参照

## トーン・スタイル
- 客観的かつ丁寧な文体
- 読者が非専門家でも理解できる平易な表現を基本とし、
  法的根拠が必要な箇所では正確な法令名・条番号を併記する
- 「問題点の指摘」だけでなく「具体的な解決策」を必ずセットで提示する"""
