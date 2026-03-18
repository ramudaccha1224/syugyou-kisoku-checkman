"""Step3: Gemini API呼び出し・リーガルチェック実行"""

from __future__ import annotations

import time

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL


def run_legal_check(
    system_prompt: str,
    document_text: str,
    max_retries: int = 3,
) -> str:
    """Gemini APIを使用して就業規則のリーガルチェックを実行する。

    Args:
        system_prompt: 動的生成されたシステムプロンプト
        document_text: 就業規則のテキスト全文
        max_retries: 最大リトライ回数

    Returns:
        Geminiからのチェック結果（Markdown文字列）
    """
    client = genai.Client(api_key=GEMINI_API_KEY)

    user_message = (
        "以下が、チェック対象の就業規則です。\n"
        "上記のチェックリストと判定基準に従い、網羅的にリーガルチェックを実施してください。\n\n"
        "---\n"
        f"{document_text}\n"
        "---"
    )

    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=65536,
                ),
            )
            return response.text or "（応答が空でした。再度お試しください。）"

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 指数バックオフ: 2, 4, 8秒
                time.sleep(wait)

    raise RuntimeError(
        f"Gemini APIの呼び出しに{max_retries}回失敗しました: {last_error}"
    )
