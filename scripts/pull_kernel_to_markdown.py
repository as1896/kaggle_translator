#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kaggle Notebook(.ipynb) → Markdown 変換（自分のEditノート含む）
- Kaggle API で .ipynb を取得（private でも OK: ~/.kaggle/kaggle.json 必須）
- nbconvert で .md へ
- 画像/添付は <slug>_files/ 下に保存
Usage:
  python3 pull_kernel_to_markdown.py --url https://www.kaggle.com/code/<user>/<slug>/edit --out out/course [--include-outputs]
  python3 pull_kernel_to_markdown.py --ref <user>/<slug> --out out/course
"""

import argparse, json, os, re, shutil, subprocess, tempfile, pathlib, sys
from typing import Optional
import nbformat
from nbconvert import MarkdownExporter

def parse_ref_from_url(url: str) -> Optional[str]:
    """
    https://www.kaggle.com/code/<user>/<slug> (/edit や /tutorial 付きでもOK)
    → <user>/<slug> を返す
    """
    m = re.search(r"https?://www\.kaggle\.com/code/([^/]+)/([^/?#]+)", url)
    if not m:
        return None
    user, slug = m.group(1), m.group(2)
    # 末尾に /edit 等が付いても上の正規表現で slug は取れている
    return f"{user}/{slug}"

def run(cmd: list[str], cwd: Optional[str] = None) -> None:
    try:
        subprocess.run(cmd, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print("ERROR running:", " ".join(cmd), file=sys.stderr)
        raise

def kaggle_pull_ipynb(kernel_ref: str, dest_dir: pathlib.Path) -> pathlib.Path:
    """
    kaggle kernels pull <ref> -p <dest_dir>
    を実行して .ipynb を取得し、そのパスを返す
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    run(["kaggle", "kernels", "pull", kernel_ref, "-p", str(dest_dir)])
    # 取得物から .ipynb を探す
    ipynb_list = list(dest_dir.glob("*.ipynb"))
    if not ipynb_list:
        # サブフォルダに入るケースも一応捜索
        ipynb_list = list(dest_dir.rglob("*.ipynb"))
    if not ipynb_list:
        raise FileNotFoundError("Downloaded files do not include an .ipynb")
    # 通常はカーネル名と同じ .ipynb が落ちる
    return ipynb_list[0]

def ipynb_to_markdown(ipynb_path: pathlib.Path, out_md: pathlib.Path, include_outputs: bool) -> None:
    """
    nbconvert MarkdownExporter を使って .md に変換
    - include_outputs=False の場合、出力を除去（テキストだけ欲しい時に）
    - 添付や画像は <stem>_files/ ディレクトリに保存
    """
    out_md.parent.mkdir(parents=True, exist_ok=True)
    resources = {
        "unique_key": out_md.stem,
        "output_files_dir": out_md.stem + "_files"
    }
    with ipynb_path.open("r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    exporter = MarkdownExporter()
    # 出力を含めない場合
    if not include_outputs:
        exporter.exclude_output_prompt = True
        exporter.exclude_input_prompt = True
        exporter.exclude_output = True

    body, res = exporter.from_notebook_node(nb, resources=resources)

    # 本文を書き出し
    out_md.write_text(body, encoding="utf-8")

    # 画像や添付を保存
    outputs = res.get("outputs", {})
    if outputs:
        files_dir = out_md.parent / resources["output_files_dir"]
        files_dir.mkdir(parents=True, exist_ok=True)
        for relname, data in outputs.items():
            (files_dir / relname).write_bytes(data)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Kaggle notebook URL (edit / tutorial でもOK)")
    ap.add_argument("--ref", help="<user>/<slug> の形式で指定する場合")
    ap.add_argument("--out", default="out/course", help="出力ディレクトリ")
    ap.add_argument("--include-outputs", action="store_true", help="ノート出力(グラフ/print等)も.mdに含める")
    args = ap.parse_args()

    kernel_ref = args.ref or (parse_ref_from_url(args.url) if args.url else None)
    if not kernel_ref:
        print("ERROR: --url か --ref を指定してください。例: --ref asta5107/exercise-a-single-neuron", file=sys.stderr)
        sys.exit(1)

    outdir = pathlib.Path(args.out)
    slug = kernel_ref.split("/", 1)[1]
    out_md = outdir / f"{slug}.md"

    with tempfile.TemporaryDirectory() as td:
        tmpdir = pathlib.Path(td)
        ipynb = kaggle_pull_ipynb(kernel_ref, tmpdir)
        ipynb_to_markdown(ipynb, out_md, include_outputs=args.include_outputs)

    print("Saved:", out_md)

if __name__ == "__main__":
    main()
