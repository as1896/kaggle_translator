#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Translate Markdown (EN -> JA) using Gemini API (token-aware, minimal splits)
- Preserves Markdown structure
- Leaves code blocks as-is
- Splits only when token limit exceeds (prefer headings; never split inside fenced code)
Usage:
  export GOOGLE_API_KEY=xxx
  python3 translate_markdown_with_gemini.py --in out --glob "*.md" --model gemini-1.5-flash
Outputs:
  <name>.ja.md next to each source file
"""

import os, sys, argparse, glob, re, time, pathlib, random, hashlib
from typing import List

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ---------------- Configurable defaults ----------------
DEFAULT_MODEL = "gemini-1.5-flash"   # 品質優先なら "gemini-1.5-pro"
# 1 リクエスト最大トークン（入力+出力）。安全側にやや小さめを選ぶ:
MAX_TOKENS_PER_REQ = 40_000
# 出力に使うトークン余白（日本語化で膨らむことがあるため）
OUTPUT_BUFFER_TOKENS = 2_000
# プロンプト固定部に使うトークン余白（概算）
PROMPT_BUFFER_TOKENS = 500
# チャンク間の待機（レート緩和）
SLEEP_BETWEEN_CHUNKS_SEC = (0.9, 1.6)  # min,max の範囲からランダム

JOIN_SEP = "\n\n"                    # チャンク結合時の区切り

PROMPT_PREFIX = """You are a professional technical translator.
Translate the following Markdown from English to Japanese.
Rules:
- Preserve ALL Markdown structure (headings, lists, tables, links).
- Do NOT translate fenced code blocks (```...```), inline code (`code`), or URLs.
- Translate only the visible link text; keep link targets unchanged.
- Keep math/LaTeX as-is.
- No extra commentary. Output ONLY translated Markdown.
"""

# Optional glossary. Example: {"robot": "ロボット"}
GLOSSARY = {
    # "Titanic": "タイタニック",
    # "Kaggle": "Kaggle",
}

def apply_glossary_jp(text: str) -> str:
    for en, jp in GLOSSARY.items():
        # 単語境界を考慮（大文字小文字はそのまま）
        text = re.sub(rf"\b{re.escape(en)}\b", jp, text)
    return text

# ---------------- Gemini client ----------------
def configure_client(model_name: str):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: set GOOGLE_API_KEY env var", file=sys.stderr)
        sys.exit(1)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)

# 安全にトークン数を数える
def count_tokens(model, text: str) -> int:
    try:
        return model.count_tokens(text).total_tokens
    except Exception:
        # 万一失敗したら概算（かなり保守的）にフォールバック
        # 英文: 1 token ≈ 4 chars 目安 → 日本語増大も考慮して 1 token ≈ 3 chars とする
        return max(1, len(text) // 3)

# ---------------- Splitting logic (token-aware, fence-safe, heading-preferred) ----------------
def split_markdown_token_aware(model, md: str) -> List[str]:
    """
    1回で入るなら分割しない。
    入らない場合のみ、見出し優先で分割（コードフェンス内は絶対に割らない）。
    """
    soft_limit = MAX_TOKENS_PER_REQ - OUTPUT_BUFFER_TOKENS - PROMPT_BUFFER_TOKENS
    if count_tokens(model, PROMPT_PREFIX + "\n\n" + md) <= soft_limit:
        return [md]

    lines = md.splitlines(keepends=True)
    chunks, buf = [], []
    fence_open = False

    def buf_text():
        return "".join(buf)

    def buf_tokens() -> int:
        # プロンプト込みで測る（安全側）
        return count_tokens(model, PROMPT_PREFIX + "\n\n" + buf_text())

    def flush():
        if buf:
            chunks.append(buf_text())
            buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        # フェンス境界の検出
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_open = not fence_open

        # 次の行を追加した場合のトークン数を見積もり
        trial = buf_text() + line
        trial_tokens = count_tokens(model, PROMPT_PREFIX + "\n\n" + trial)

        if trial_tokens > soft_limit and not fence_open:
            # ここで切る（見出し優先: 直前に見出しが始まっていればそこで割れているはず）
            flush()
            # すぐに行を新しいバッファに入れ直す（行そのものが大きすぎる場合は強制的に入れる）
            buf.append(line)
            # 万一1行で超えるような極端なケースは、そのまま1チャンクとして扱う
            if buf_tokens() > soft_limit:
                flush()
            i += 1
            continue

        # 見出しで始まるなら出来るだけチャンク境界を合わせる（ただしバッファが十分大きい場合）
        is_heading = (not fence_open) and re.match(r"^#{1,6}\s", line)
        if is_heading and buf and buf_tokens() > soft_limit * 0.6:
            # 見出し行の前で切る
            flush()

        # 追加
        buf.append(line)
        i += 1

    flush()
    return chunks

# ---------------- Translate with retry ----------------
class RateLimitError(Exception):
    pass

@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type((RateLimitError, OSError))
)
def translate_chunk(model, text: str) -> str:
    prompt = PROMPT_PREFIX + "\n\n" + text
    try:
        resp = model.generate_content(prompt)
    except Exception as e:
        msg = str(e).lower()
        # 429 / quota / temporarily / rate limit の気配があればリトライ
        if "429" in msg or "rate" in msg or "quota" in msg or "temporar" in msg or "exceeded" in msg:
            raise RateLimitError(e)
        raise
    out = (resp.text or "").strip()
    return out

# ---------------- File-level translate ----------------
def file_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def translate_file(model, src_path: pathlib.Path, out_suffix: str = ".ja.md"):
    src = src_path.read_text(encoding="utf-8")
    chunks = split_markdown_token_aware(model, src)
    print(f"Split into {len(chunks)} chunk(s).")

    out_parts = []
    for i, ch in enumerate(chunks, 1):
        print(f"  - translating chunk {i}/{len(chunks)} (~{count_tokens(model, ch)} tokens input)")
        out_parts.append(translate_chunk(model, ch))
        time.sleep(random.uniform(*SLEEP_BETWEEN_CHUNKS_SEC))  # レート緩和

    out_text = JOIN_SEP.join(out_parts)
    out_text = apply_glossary_jp(out_text)

    dst = src_path.with_suffix(out_suffix)
    dst.write_text(out_text, encoding="utf-8")
    print(f"✅ wrote {dst}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", required=True, help="Input dir containing .md files")
    ap.add_argument("--glob", default="*.md", help="Glob pattern (default: *.md)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name")
    args = ap.parse_args()

    model = configure_client(args.model)
    paths = sorted(pathlib.Path(args.in_dir).glob(args.glob))
    if not paths:
        print("No files matched. Check --in and --glob.")
        sys.exit(0)

    for p in paths:
        # 既に .ja.md のものはスキップ
        if p.suffix == ".md" and not p.name.endswith(".ja.md"):
            print(f"Translating: {p}")
            translate_file(model, p)
        else:
            print(f"Skip: {p} (already ja or not .md)")

if __name__ == "__main__":
    main()
