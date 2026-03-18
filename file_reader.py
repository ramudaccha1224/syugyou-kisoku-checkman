"""PDF/DOCX テキスト抽出"""

from __future__ import annotations

from io import BytesIO

from PyPDF2 import PdfReader
from docx import Document


def extract_text(uploaded_file) -> str:
    """アップロードされたファイルからテキストを抽出する。

    Args:
        uploaded_file: Streamlit の UploadedFile オブジェクト

    Returns:
        抽出されたテキスト文字列
    """
    name: str = uploaded_file.name.lower()
    data = uploaded_file.read()

    if name.endswith(".pdf"):
        return _extract_pdf(data)
    elif name.endswith(".docx"):
        return _extract_docx(data)
    else:
        raise ValueError(f"未対応のファイル形式です: {name}")


def extract_multiple(uploaded_files: list) -> dict[str, str]:
    """複数ファイルからテキストを抽出する。

    Args:
        uploaded_files: Streamlit の UploadedFile オブジェクトのリスト

    Returns:
        {ファイル名: 抽出テキスト} の辞書
    """
    results: dict[str, str] = {}
    for f in uploaded_files:
        f.seek(0)
        results[f.name] = extract_text(f)
    return results


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_docx(data: bytes) -> str:
    doc = Document(BytesIO(data))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)
