"""PDF テキスト抽出（OCRフォールバック付き）"""

from __future__ import annotations

from io import BytesIO

from PyPDF2 import PdfReader


def extract_text(uploaded_file) -> str:
    """アップロードされたPDFファイルからテキストを抽出する。

    1. まず PyPDF2 でテキスト抽出を試みる（テキスト埋め込みPDF向け）
    2. テキストが十分に取れなければ OCR にフォールバック（スキャンPDF向け）
    """
    name: str = uploaded_file.name.lower()
    data = uploaded_file.read()

    if not name.endswith(".pdf"):
        raise ValueError(f"未対応のファイル形式です: {name}（PDFのみ対応）")

    # まず通常のテキスト抽出を試行
    text = _extract_pdf_text(data)

    # テキストがほぼ空ならスキャンPDFと判断し、OCRにフォールバック
    if _is_text_insufficient(text):
        ocr_text = _extract_pdf_ocr(data)
        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
            return ocr_text

    return text


def extract_multiple(uploaded_files: list) -> dict[str, str]:
    """複数ファイルからテキストを抽出する。"""
    results: dict[str, str] = {}
    for f in uploaded_files:
        f.seek(0)
        results[f.name] = extract_text(f)
    return results


def _extract_pdf_text(data: bytes) -> str:
    """PyPDF2 によるテキスト抽出（テキスト埋め込みPDF用）"""
    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _is_text_insufficient(text: str) -> bool:
    """抽出テキストが不十分か（スキャンPDFの可能性があるか）判定する。

    - 完全に空、または1ページあたり平均30文字未満ならスキャンPDFとみなす
    """
    stripped = text.strip()
    if not stripped:
        return True
    # 極端に短いテキスト（ヘッダーだけ等）もOCR対象
    if len(stripped) < 50:
        return True
    return False


def _extract_pdf_ocr(data: bytes) -> str:
    """pdf2image + pytesseract によるOCRテキスト抽出（スキャンPDF用）"""
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError:
        # OCRライブラリ未インストール時は空文字を返す
        return ""

    try:
        # PDF → 画像に変換（300dpiで十分な精度）
        images = convert_from_bytes(data, dpi=300)

        ocr_pages: list[str] = []
        for img in images:
            # 日本語 + 英語でOCR実行
            page_text = pytesseract.image_to_string(img, lang="jpn+eng")
            ocr_pages.append(page_text)

        return "\n".join(ocr_pages)
    except Exception:
        return ""
