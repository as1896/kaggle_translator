# app/app.py
import sys
import os
import re
import time
import subprocess
from pathlib import Path

import streamlit as st
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# =========================================================
# パス解決（このファイルの位置を基点に、プロジェクトルート＆scripts を解決）
# =========================================================
APP_DIR = Path(__file__).resolve().parent                # .../project/app
PROJECT_ROOT = APP_DIR.parent                            # .../project
SCRIPTS_DIR = (PROJECT_ROOT / "scripts").resolve()       # .../project/scripts
OUT_DIR = (PROJECT_ROOT / "out").resolve()               # 出力はプロジェクト直下 out/

def py(script_name: str) -> list[str]:
    """実行中の Python で scripts/<script_name> を呼ぶ引数リストを返す"""
    return [sys.executable, str(SCRIPTS_DIR / script_name)]

# =========================================================
# Selenium driver 共通
# =========================================================
def build_driver(headless: bool = True):
    opt = webdriver.ChromeOptions()
    if headless:
        opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opt)

def normalize_comp_url(inp: str) -> str:
    url = inp.strip().rstrip("/")
    m = re.match(r"^(https?://www\.kaggle\.com/competitions/[^/]+)", url)
    return m.group(1) if m else url

def normalize_slug(url: str) -> str:
    slug = url.strip().rstrip("/").split("/")[-1]
    return re.sub(r"[^a-zA-Z0-9._-]", "-", slug) or "kaggle_course"

def normalize_kernel_slug(url: str) -> str:
    # 例: https://www.kaggle.com/code/asta5107/exercise-a-single-neuron/edit → exercise-a-single-neuron
    parts = url.strip().rstrip("/").split("/")
    if len(parts) >= 2:
        last = parts[-1]
        if last in ("edit", "script"):  # editビューなど
            last = parts[-2]
        return re.sub(r"[^a-zA-Z0-9._-]", "-", last) or "kaggle_kernel"
    return "kaggle_kernel"

# =========================================================
# Discussion 一覧取得
# =========================================================
def fetch_discussion_list(comp_base_url: str, page: int = 1, max_items: int = 30):
    list_url = f"{comp_base_url}/discussion"
    if page > 1:
        list_url += f"?page={page}"

    d = build_driver(headless=True)
    threads = []
    try:
        d.get(list_url)
        WebDriverWait(d, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/discussion/']"))
        )
        # 軽くスクロール
        for _ in range(3):
            d.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.3)

        soup = BeautifulSoup(d.page_source, "html.parser")
        seen = set()
        for a in soup.select("a[href*='/discussion/']"):
            href = a.get("href", "")
            if not re.search(r"/discussion/\d+/?$", href):
                continue
            full = "https://www.kaggle.com" + href if href.startswith("/") else href
            if full in seen:
                continue
            title = a.get_text(strip=True)
            if re.fullmatch(r"comments?", title, flags=re.IGNORECASE):
                continue
            threads.append({"title": title, "url": full})
            seen.add(full)
            if len(threads) >= max_items:
                break
    finally:
        d.quit()
    return threads

# =========================================================
# Streamlit アプリ
# =========================================================
st.set_page_config(page_title="Kaggle Competition Translator", layout="wide")
st.title("Kaggle Competition Translator")

# ====== 共通出力先 ======
OUT_DIR.mkdir(exist_ok=True)
(out_course := OUT_DIR / "course").mkdir(parents=True, exist_ok=True)
(out_kernel := OUT_DIR / "kernel").mkdir(parents=True, exist_ok=True)

# ====== コンペURL入力（既存） ======
url_in = st.text_input(
    "Kaggle Competition URL",
    "https://www.kaggle.com/competitions/titanic/overview",
    help="overview / data / rules / discussion どれでもOK（自動でベースURLに正規化）"
)
comp_base = normalize_comp_url(url_in)

# ===== タブ構成 =====
tabs = st.tabs([
    "Overview", "Data", "Rules",
    "Discussion",
    "Notebook/Course (iframe)",
    "My Notebook (API)"
])

# ---------- Overview / Data / Rules ----------
def show_md_pair(basename: str, tab):
    en = OUT_DIR / f"{basename}.md"
    ja = OUT_DIR / f"{basename}.ja.md"
    with tab:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"{basename}.md (EN)")
            if en.exists(): st.markdown(en.read_text(encoding="utf-8"))
            else: st.info("まだ生成されていません。")
        with col2:
            st.subheader(f"{basename}.ja.md (JA)")
            if ja.exists(): st.markdown(ja.read_text(encoding="utf-8"))
            else: st.info("まだ翻訳されていません。")

with st.sidebar:
    st.markdown("### 共通操作（コンペ用）")
    run_tabs = st.button("① Overview/Data/Rules を取得→翻訳（英→日）")
    os.environ.setdefault("GOOGLE_API_KEY", "")
    st.checkbox("API Key 設定済み", value=bool(os.getenv("GOOGLE_API_KEY")), disabled=True)

if run_tabs:
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("環境変数 GOOGLE_API_KEY が未設定です。`export GOOGLE_API_KEY=...` を実行してください。")
    else:
        with st.status("Fetching English Markdown ...", expanded=True) as s:
            s.write("saving overview/data/rules ...")
            subprocess.run(py("save_kaggle_comp_markdown.py") + ["--url", comp_base, "--out", str(OUT_DIR)], check=True)
            s.update(label="Translating with Gemini ...")
            subprocess.run(py("translate_markdown_with_gemini.py") + ["--in", str(OUT_DIR), "--glob", "*.md"], check=True)
            s.update(label="Done!")

# EN/JA 表示（コンペ）
show_md_pair("overview", tabs[0])
show_md_pair("data", tabs[1])
show_md_pair("rules", tabs[2])

# ---------- Discussion ----------
with tabs[3]:
    st.subheader("Discussion — ページ送り＋ページ指定＋日本語化（任意）")

    if "page" not in st.session_state:
        st.session_state.page = 1

    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        if st.button("◀ 前のページ"):
            if st.session_state.page > 1:
                st.session_state.page -= 1
    with col2:
        if st.button("次のページ ▶"):
            st.session_state.page += 1
    with col3:
        page_input = st.number_input("ページ指定", min_value=1, step=1,
                                     value=st.session_state.page, key="page_input")
        if page_input != st.session_state.page:
            st.session_state.page = page_input

    st.write(f"### 現在のページ: {st.session_state.page}")

    if comp_base:
        threads = fetch_discussion_list(comp_base, page=st.session_state.page)
        if not threads:
            st.info("スレッドが見つかりませんでした。")
        else:
            for i, t in enumerate(threads, 1):
                st.markdown(f"**{i}. [{t['title']}]({t['url']})**")

# ---------- Notebook/Course タブ（Selenium/iframe版） ----------
def show_course_md_pair(slug: str, tab):
    en = out_course / f"{slug}.md"
    ja = out_course / f"{slug}.ja.md"
    with tab:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"{slug}.md (EN)")
            if en.exists(): st.markdown(en.read_text(encoding="utf-8"))
            else: st.info("まだ生成されていません。")
        with col2:
            st.subheader(f"{slug}.ja.md (JA)")
            if ja.exists(): st.markdown(ja.read_text(encoding="utf-8"))
            else: st.info("まだ翻訳されていません。")

with tabs[4]:
    st.subheader("Notebook / Course → 英語MD取得 & 日本語訳（iframe方式）")
    nb_url = st.text_input(
        "Notebook/Course URL",
        "https://www.kaggle.com/code/ryanholbrook/a-single-neuron",
        help="例) https://www.kaggle.com/code/<author>/<slug>"
    )
    nb_slug = normalize_slug(nb_url)

    colA, colB, colC = st.columns([1,1,2])
    with colA:
        fetch_nb = st.button("② 英語MDを取得")
    with colB:
        translate_nb = st.button("③ 日本語に翻訳")
    with colC:
        st.write(f"保存先: `out/course/{nb_slug}.md` / `out/course/{nb_slug}.ja.md`")

    if fetch_nb:
        with st.status("Fetching notebook markdown ...", expanded=True) as s:
            s.write("Saving EN markdown ...")
            subprocess.run(
                py("save_kaggle_course_markdown.py") + ["--url", nb_url, "--out", str(out_course)],
                check=True
            )
            s.update(label="Done!")

    if translate_nb:
        if not os.getenv("GOOGLE_API_KEY"):
            st.error("環境変数 GOOGLE_API_KEY が未設定です。`export GOOGLE_API_KEY=...` を実行してください。")
        else:
            with st.status("Translating with Gemini ...", expanded=True) as s:
                subprocess.run(
                    py("translate_markdown_with_gemini.py") + ["--in", str(out_course), "--glob", f"{nb_slug}.md"],
                    check=True
                )
                s.update(label="Done!")

    show_course_md_pair(nb_slug, tabs[4])

# ---------- My Notebook (API) タブ（Kaggle API 方式） ----------
def show_kernel_md_pair(slug: str, tab):
    en = out_kernel / f"{slug}.md"
    ja = out_kernel / f"{slug}.ja.md"
    with tab:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"{slug}.md (EN)")
            if en.exists(): st.markdown(en.read_text(encoding="utf-8"))
            else: st.info("まだ生成されていません。")
        with col2:
            st.subheader(f"{slug}.ja.md (JA)")
            if ja.exists(): st.markdown(ja.read_text(encoding="utf-8"))
            else: st.info("まだ翻訳されていません。")

with tabs[5]:
    st.subheader("My Notebook (API) → 英語MD取得 & 日本語訳（Kaggle API 使用）")

    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if not kaggle_json.exists():
        st.warning("`~/.kaggle/kaggle.json` が見つかりません。Kaggle APIキーを配置してください。")
    else:
        try:
            mode = kaggle_json.stat().st_mode & 0o777
            if mode not in (0o600, 0o400):
                st.info("ヒント: `chmod 600 ~/.kaggle/kaggle.json` を実行すると警告が出なくなります。")
        except Exception:
            pass

    api_url = st.text_input(
        "自分のNotebook URL（view/editどちらでも可）",
        "https://www.kaggle.com/",
        help="例) https://www.kaggle.com/code/<yourname>/<slug> または /edit"
    )
    api_slug = normalize_kernel_slug(api_url)

    include_outputs = st.checkbox("出力（図表/print等）も含める (--include-outputs)", value=True)

    colA, colB, colC = st.columns([1,1,2])
    with colA:
        fetch_kernel = st.button("④ 英語MDを取得（API）")
    with colB:
        translate_kernel = st.button("⑤ 日本語に翻訳")
    with colC:
        st.write(f"保存先: `out/kernel/{api_slug}.md` / `out/kernel/{api_slug}.ja.md`")

    if fetch_kernel:
        out_kernel.mkdir(parents=True, exist_ok=True)
        with st.status("Pulling kernel via Kaggle API ...", expanded=True) as s:
            cmd = py("pull_kernel_to_markdown.py") + ["--url", api_url, "--out", str(out_kernel)]
            if include_outputs:
                cmd.append("--include-outputs")
            s.write("Running: " + " ".join(cmd))
            subprocess.run(cmd, check=True)
            s.update(label="Done!")

    if translate_kernel:
        if not os.getenv("GOOGLE_API_KEY"):
            st.error("環境変数 GOOGLE_API_KEY が未設定です。`export GOOGLE_API_KEY=...` を実行してください。")
        else:
            with st.status("Translating with Gemini ...", expanded=True) as s:
                subprocess.run(
                    py("translate_markdown_with_gemini.py") + ["--in", str(out_kernel), "--glob", f"{api_slug}.md"],
                    check=True
                )
                s.update(label="Done!")

    show_kernel_md_pair(api_slug, tabs[5])
