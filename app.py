"""就業規則チェックマン - Streamlit メインアプリ"""

from __future__ import annotations

import streamlit as st

from config import load_checklist, load_knowledge, GEMINI_API_KEY
from file_reader import extract_text, extract_multiple
from hearing import get_hearing_items, build_hearing_result
from prompt_builder import build_system_prompt
from analyzer import run_legal_check
from ref_detector import detect_external_references, filter_unresolved_references

# --- ページ設定 ---
st.set_page_config(
    page_title="就業規則チェックマン",
    page_icon="📋",
    layout="wide",
)

st.title("📋 就業規則チェックマン")
st.caption("AIが社労士の視点で、あなたの就業規則をリーガルチェックします。")


# ========================================
# session_state 初期化
# ========================================
def init_state():
    defaults = {
        "step": 1,
        "uploaded_texts": {},       # {ファイル名: テキスト}
        "document_text": "",        # 全ファイル結合テキスト
        "hearing_result": None,
        "unresolved_refs": [],      # 未解決の別規程参照
        "supplement_skipped": False,
        "check_result": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_state()

# --- APIキーチェック ---
if not GEMINI_API_KEY:
    st.error(
        "Gemini APIキーが設定されていません。\n\n"
        "`.env` ファイルに `GEMINI_API_KEY=あなたのAPIキー` を記載してください。"
    )
    st.stop()

# --- データ読み込み ---
checklist = load_checklist()
knowledge = load_knowledge()

# ========================================
# サイドバー: ファイルアップロード（複数可）
# ========================================
with st.sidebar:
    st.header("書類をアップロード")
    uploaded_files = st.file_uploader(
        "PDF ファイルを選択（複数可）",
        type=["pdf"],
        accept_multiple_files=True,
        help="就業規則の本体に加え、賃金規程などの別紙がある場合はまとめてアップロードしてください。",
    )

    if uploaded_files:
        try:
            texts = extract_multiple(uploaded_files)
            if any(t.strip() for t in texts.values()):
                st.session_state["uploaded_texts"] = texts
                # 全テキスト結合（ファイル名ヘッダー付き）
                combined_parts = []
                for fname, text in texts.items():
                    if text.strip():
                        combined_parts.append(
                            f"\n{'='*40}\n【{fname}】\n{'='*40}\n{text}"
                        )
                st.session_state["document_text"] = "\n".join(combined_parts)

                for fname, text in texts.items():
                    char_count = len(text)
                    if char_count > 0:
                        st.success(f"✅ {fname}（{char_count:,} 文字）")
                    else:
                        st.warning(f"⚠ {fname}（テキスト抽出不可）")
            else:
                st.warning("いずれのファイルからもテキストを抽出できませんでした。")
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {e}")

    st.divider()
    st.markdown(
        "**使い方**\n"
        "1. 就業規則（＋別紙）をアップロード\n"
        "2. ヒアリングに回答\n"
        "3. 不足書類があれば追加アップロード\n"
        "4. チェック結果を確認"
    )

# ========================================
# メイン: ステップ表示
# ========================================
step = st.session_state["step"]

# --- ステップインジケーター ---
step_labels = [
    "Step 1: ヒアリング",
    "Step 2: 不足書類の確認",
    "Step 3: チェック実行",
    "Step 4: 結果確認",
]
cols = st.columns(len(step_labels))
for i, (col, label) in enumerate(zip(cols, step_labels), start=1):
    if i < step:
        col.success(f"✅ {label}")
    elif i == step:
        col.info(f"▶ {label}")
    else:
        col.markdown(f"⬜ {label}")

st.divider()

# ========================================
# Step 1: ヒアリング
# ========================================
if step == 1:
    st.header("Step 1: 事前ヒアリング（問診）")
    st.markdown(
        "貴社の制度の有無を確認します。\n"
        "以下の質問に「定めている」「定めていない」「分からない」でお答えください。"
    )

    if not st.session_state["document_text"]:
        st.warning("まず、サイドバーから就業規則ファイルをアップロードしてください。")
        st.stop()

    hearing_items = get_hearing_items(checklist)

    with st.form("hearing_form"):
        raw_answers: dict[str, str] = {}

        # カテゴリごとにグループ化して表示
        current_category = ""
        for item in hearing_items:
            cat_label = checklist.categories.get(item.category.value, "")
            if cat_label != current_category:
                current_category = cat_label
                st.subheader(cat_label)

            raw_answers[item.id] = st.radio(
                f"**{item.item_name}**\n\n{item.hearing_question}",
                options=["定めている", "定めていない", "分からない"],
                index=2,  # デフォルト「分からない」
                key=f"hearing_{item.id}",
                horizontal=True,
            )

        submitted = st.form_submit_button(
            "ヒアリング完了 → 次へ",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            hearing_result = build_hearing_result(hearing_items, raw_answers)
            st.session_state["hearing_result"] = hearing_result

            # 別規程参照を検出
            doc_text = st.session_state["document_text"]
            uploaded_texts = st.session_state["uploaded_texts"]
            refs = detect_external_references(doc_text)
            unresolved = filter_unresolved_references(
                refs,
                list(uploaded_texts.keys()),
                uploaded_texts,
            )
            st.session_state["unresolved_refs"] = unresolved
            st.session_state["supplement_skipped"] = False

            if unresolved:
                st.session_state["step"] = 2  # 不足書類の確認へ
            else:
                st.session_state["step"] = 3  # 不足なし → チェック実行へ
            st.rerun()

# ========================================
# Step 2: 不足書類の確認・追加アップロード
# ========================================
elif step == 2:
    st.header("Step 2: 不足書類の確認")

    unresolved = st.session_state["unresolved_refs"]

    st.warning(
        "就業規則の中に、以下の別規程・別紙への参照が見つかりましたが、"
        "該当する書類がアップロードされていないようです。"
    )

    # 検出された参照を条文付きで表示
    for i, ref in enumerate(unresolved, 1):
        # ヘッダー: 規程名
        header = f"**{i}. {ref.doc_name}**"
        st.markdown(header)

        # 条番号・タイトル + 条文全文
        if ref.article_number:
            title_part = f"（{ref.article_title}）" if ref.article_title else ""
            st.markdown(f"**{ref.article_number}　{title_part}**")
        st.code(ref.article_text, language=None)

    st.divider()

    st.markdown("該当する書類があればアップロードしてください。なければスキップして構いません。")

    # 追加アップロード
    supplement_files = st.file_uploader(
        "追加書類をアップロード（複数可）",
        type=["pdf"],
        accept_multiple_files=True,
        key="supplement_uploader",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "追加書類を読み込んでチェック開始",
            type="primary",
            use_container_width=True,
            disabled=not supplement_files,
        ):
            # 追加ファイルのテキストを抽出して結合
            new_texts = extract_multiple(supplement_files)
            uploaded_texts = st.session_state["uploaded_texts"]
            uploaded_texts.update(new_texts)
            st.session_state["uploaded_texts"] = uploaded_texts

            # 全テキスト再結合
            combined_parts = []
            for fname, text in uploaded_texts.items():
                if text.strip():
                    combined_parts.append(
                        f"\n{'='*40}\n【{fname}】\n{'='*40}\n{text}"
                    )
            st.session_state["document_text"] = "\n".join(combined_parts)
            st.session_state["step"] = 3
            st.rerun()

    with col2:
        if st.button(
            "スキップ（別規程なしとして判定）",
            use_container_width=True,
        ):
            st.session_state["supplement_skipped"] = True
            st.session_state["step"] = 3
            st.rerun()

# ========================================
# Step 3: チェック実行
# ========================================
elif step == 3:
    st.header("Step 3: リーガルチェック実行中...")

    hearing_result = st.session_state["hearing_result"]
    document_text = st.session_state["document_text"]

    if not hearing_result or not document_text:
        st.error("ヒアリング結果またはドキュメントが見つかりません。")
        st.session_state["step"] = 1
        st.rerun()

    # システムプロンプト生成
    system_prompt = build_system_prompt(checklist, knowledge, hearing_result)

    # スキップされた場合の追加指示
    if st.session_state.get("supplement_skipped"):
        supplement_note = (
            "\n\n## 追加指示: 別規程について\n"
            "ユーザーは別規程・別紙の追加提出をスキップしました。\n"
            "就業規則内に「別に定める」「別紙参照」等の委任条項がある場合、\n"
            "委任先の規程は存在しないものとして判定してください。\n"
            "該当する項目は「不備」として指摘し、就業規則本体に記載するか、\n"
            "別規程を整備する必要がある旨を助言してください。"
        )
        system_prompt += supplement_note

    # ヒアリングサマリー表示
    with st.expander("ヒアリング回答サマリー", expanded=False):
        for a in hearing_result.answers:
            icon = {"yes": "✅", "no": "❌", "unknown": "❓"}.get(a.answer.value, "")
            label = {"yes": "定めている", "no": "定めていない", "unknown": "分からない"}.get(
                a.answer.value, ""
            )
            st.markdown(f"- {icon} **{a.item_name}**: {label}")

    # アップロード済みファイル一覧
    with st.expander("アップロード済みファイル", expanded=False):
        for fname in st.session_state["uploaded_texts"]:
            st.markdown(f"- 📄 {fname}")
        if st.session_state.get("supplement_skipped"):
            st.info("ℹ 別規程の追加アップロードはスキップされました。")

    # Gemini API呼び出し
    with st.spinner("チェックマンがリーガルチェックを実行中です... しばらくお待ちください。"):
        try:
            result = run_legal_check(system_prompt, document_text)
            st.session_state["check_result"] = result
            st.session_state["step"] = 4
            st.rerun()
        except RuntimeError as e:
            st.error(f"エラーが発生しました: {e}")
            if st.button("リトライ"):
                st.rerun()

# ========================================
# Step 4: 結果表示
# ========================================
elif step == 4:
    st.header("Step 4: リーガルチェック結果")

    result = st.session_state["check_result"]
    if result:
        st.markdown(result)
    else:
        st.warning("結果がありません。")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("最初からやり直す", use_container_width=True):
            for key in [
                "step", "uploaded_texts", "document_text",
                "hearing_result", "unresolved_refs",
                "supplement_skipped", "check_result",
            ]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with col2:
        if st.button("同じ規則で再チェック", use_container_width=True):
            st.session_state["step"] = 1
            st.session_state["hearing_result"] = None
            st.session_state["unresolved_refs"] = []
            st.session_state["supplement_skipped"] = False
            st.session_state["check_result"] = ""
            st.rerun()
