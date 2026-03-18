"""PDF テキスト抽出"""

from __future__ import annotations

from io import BytesIO

from PyPDF2 import PdfReader


def extract_text(uploaded_file) -> str:
    """アップロードされたPDFファイルからテキストを抽出する。

    Args:
        uploaded_file: Streamlit の UploadedFile オブジェクト

    Returns:
        抽出されたテキスト文字列
    """
    name: str = uploaded_file.name.lower()
    data = uploaded_file.read()

    if name.endswith(".pdf"):
        return _extract_pdf(data)
    else:
        raise ValueError(f"未対応のファイル形式です: {name}（PDFのみ対応）")


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
