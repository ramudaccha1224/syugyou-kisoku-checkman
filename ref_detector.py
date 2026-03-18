"""就業規則テキスト内の別規程参照を検出する"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExternalReference:
    """検出された別規程への参照"""
    matched_text: str       # マッチした原文フレーズ
    doc_name: str           # 推定される別規程名（例: 賃金規程）
    article_number: str     # 条番号（例: 第30条）。不明なら空文字
    article_title: str      # 条文タイトル（例: 賃金）。不明なら空文字
    article_text: str       # 該当条文の全文


# ========================================
# 自己参照の除外パターン
# ========================================
# 「この規則」「本規程」「前項の規定」「第○条の規定」等は
# 同一文書内の参照であり、別規程への参照ではない。
_SELF_REF_PATTERNS = re.compile(
    r"(?:この|本|当)\s*(?:規則|規程|規定)"
    r"|前[項条]の(?:規定|定め)"
    r"|次[項条]の(?:規定|定め)"
    r"|第[\d０-９]+[項条]の(?:規定|定め)"
    r"|同[項条]の(?:規定|定め)"
    r"|各号"
)

# ========================================
# 条文境界の検出パターン
# ========================================
# 「第○条」「第○条の○」で始まる行を条文の区切りとみなす
_ARTICLE_HEAD = re.compile(
    r"(?:^|\n)\s*(第[\d０-９]+条(?:の[\d０-９]+)?)"
)
# 条文タイトル: 第○条の直後の括弧（全角・半角）内
_ARTICLE_TITLE = re.compile(
    r"第[\d０-９]+条(?:の[\d０-９]+)?\s*[（(]\s*(.+?)\s*[）)]"
)

# ========================================
# 別規程への参照を検出するパターン
# ========================================
# 規程名に使われる文字（助詞・句読点を除外）
_DOC_NAME_CHAR = r"[^\sはがをにでとも、,。）)（(「」『』]"

_REFERENCE_PATTERNS = [
    # 「別に定める〜規程」「別途定める〜規程」
    re.compile(rf"別[にと途]?\s*定める\s*({_DOC_NAME_CHAR}{{2,15}}(?:規程|規定|規則))"),
    # 「別途〜規程に委ねる/で定める」
    re.compile(rf"別途[、,]?\s*({_DOC_NAME_CHAR}{{2,15}}(?:規程|規定|規則))\s*(?:に委ねる|で定める|により定める|に委任する|による)"),
    # 「〜規程に定める/による/の定めるところによる」
    re.compile(rf"({_DOC_NAME_CHAR}{{2,15}}(?:規程|規定|規則))\s*(?:に(?:定める|よる|委ねる|委任する)|で定める|の定めるところによる)"),
    # 「別紙」「別紙参照」「別紙○」
    re.compile(r"(別紙[\s\d０-９]*)(?:参照|のとおり|に定める|による)"),
    # 「〜については別に定める」
    re.compile(rf"({_DOC_NAME_CHAR}{{2,10}}(?:に関する事項|については|に関しては))[、,]?\s*別に定める"),
]

# ファイル名正規化用
_NORM_PATTERN = re.compile(r"[\s\u3000._\-（）()【】\[\]]+")


# ========================================
# 条文パーサー
# ========================================

@dataclass
class _Article:
    """パースされた条文"""
    number: str         # 例: "第30条"
    title: str          # 例: "賃金" （なければ空文字）
    text: str           # 条文全文（番号・タイトル含む）
    start: int          # テキスト内の開始位置
    end: int            # テキスト内の終了位置


def _parse_articles(text: str) -> list[_Article]:
    """テキストを条文単位に分割する。"""
    heads = list(_ARTICLE_HEAD.finditer(text))
    if not heads:
        return []

    articles: list[_Article] = []
    for i, head in enumerate(heads):
        start = head.start()
        # 次の条文の開始位置、またはテキスト末尾
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        article_text = text[start:end].strip()
        number = head.group(1)

        # タイトル抽出
        title_match = _ARTICLE_TITLE.search(article_text[:80])
        title = title_match.group(1) if title_match else ""

        articles.append(_Article(
            number=number,
            title=title,
            text=article_text,
            start=start,
            end=end,
        ))

    return articles


def _find_article_at(articles: list[_Article], position: int) -> _Article | None:
    """テキスト内の位置から、その位置を含む条文を返す。"""
    for art in articles:
        if art.start <= position < art.end:
            return art
    return None


# ========================================
# メイン関数
# ========================================

def detect_external_references(text: str) -> list[ExternalReference]:
    """テキスト内の別規程への参照を検出する。

    自己参照（「この規則」「前項の規定」等）は除外し、
    条文番号・タイトル・全文を付与して返す。
    """
    articles = _parse_articles(text)
    raw_refs: list[ExternalReference] = []

    for pattern in _REFERENCE_PATTERNS:
        for match in pattern.finditer(text):
            full_match = match.group(0)
            doc_name = (
                match.group(1)
                if match.lastindex and match.group(1)
                else _infer_doc_name(full_match)
            )

            if not doc_name:
                continue

            # 自己参照チェック: マッチ周辺のテキストに自己参照パターンがあれば除外
            check_start = max(0, match.start() - 5)
            check_end = min(len(text), match.end() + 5)
            surrounding = text[check_start:check_end]
            if _SELF_REF_PATTERNS.search(surrounding):
                continue

            # doc_name 自体が自己参照的か確認
            if _SELF_REF_PATTERNS.search(doc_name):
                continue

            # 該当条文を特定
            article = _find_article_at(articles, match.start())
            if article:
                art_number = article.number
                art_title = article.title
                art_text = article.text
            else:
                # 条文構造が不明な場合、前後の行を文脈として使用
                art_number = ""
                art_title = ""
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                art_text = text[start:end].replace("\n", " ").strip()

            raw_refs.append(ExternalReference(
                matched_text=full_match,
                doc_name=doc_name,
                article_number=art_number,
                article_title=art_title,
                article_text=art_text,
            ))

    return _deduplicate(raw_refs)


def filter_unresolved_references(
    refs: list[ExternalReference],
    uploaded_filenames: list[str],
    uploaded_texts: dict[str, str],
) -> list[ExternalReference]:
    """アップロード済みファイルでカバーされていない参照のみを返す。"""
    if not refs:
        return []

    norm_filenames = {_normalize(name) for name in uploaded_filenames}

    # 各ファイルのタイトル（先頭80文字以内）を取得
    file_titles: list[str] = []
    for text in uploaded_texts.values():
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped:
                file_titles.append(stripped[:80])
                break

    unresolved: list[ExternalReference] = []

    for ref in refs:
        norm_doc = _normalize(ref.doc_name)

        # 汎用参照はスキップ
        if ref.doc_name.endswith("については") or ref.doc_name.endswith("に関する事項"):
            continue

        # ファイル名でカバー済みか
        if any(norm_doc in fn for fn in norm_filenames):
            continue

        # タイトル行でカバー済みか
        if any(ref.doc_name in title for title in file_titles):
            continue

        unresolved.append(ref)

    return unresolved


# ========================================
# ユーティリティ
# ========================================

def _deduplicate(refs: list[ExternalReference]) -> list[ExternalReference]:
    """重複する参照を除去する。"""
    if not refs:
        return []

    groups: dict[str, ExternalReference] = {}
    for ref in refs:
        norm = _normalize(ref.doc_name)
        merged = False
        for existing_norm in list(groups.keys()):
            if norm in existing_norm:
                groups[norm] = ref
                if existing_norm != norm:
                    del groups[existing_norm]
                merged = True
                break
            elif existing_norm in norm:
                merged = True
                break
        if not merged:
            groups[norm] = ref

    return list(groups.values())


def _infer_doc_name(matched_text: str) -> str:
    """マッチしたテキストから規程名を推定する"""
    if "別紙" in matched_text:
        return matched_text.strip()
    if "別に定める" in matched_text or "別途" in matched_text:
        return matched_text.strip()
    return matched_text.strip()


def _normalize(text: str) -> str:
    """比較用にテキストを正規化する"""
    result = _NORM_PATTERN.sub("", text)
    for ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
        result = result.replace(ext, "")
    return result.lower()
