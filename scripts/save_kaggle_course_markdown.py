#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Save entire Kaggle Learn/Notebook page to Markdown by fetching the rendered iframe HTML.

import re, time, sys, pathlib, requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import markdownify

# ---------- webdriver ----------
def build_driver(headless: bool = True) -> webdriver.Chrome:
    opt = webdriver.ChromeOptions()
    if headless:
        opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument("--disable-blink-features=AutomationControlled")
    opt.add_argument("--disable-features=Translate,AutomationControlled")
    opt.add_experimental_option("excludeSwitches", ["enable-automation"])
    opt.add_experimental_option("useAutomationExtension", False)
    opt.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opt)

# ---------- html -> markdown ----------
def html2md(html: str) -> str:
    # ← convert パラメータを削除（strip だけにする）
    return markdownify.markdownify(
        html,
        heading_style="ATX",
        strip=["script", "style", "svg", "iframe"],
    ).strip()

def normalize_slug(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return re.sub(r"[^a-zA-Z0-9._-]", "-", slug) or "kaggle_notebook"

# ---------- helpers ----------
def fetch_iframe_src(page_url: str, timeout: int = 30) -> tuple[str, str]:
    d = build_driver(headless=True)
    try:
        d.get(page_url)
        page_title = d.title or ""
        iframe = WebDriverWait(d, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#rendered-kernel-content"))
        )
        src = iframe.get_attribute("src")
        if not src:
            raise RuntimeError("iframe src not found")
        return src, page_title
    finally:
        d.quit()

def fetch_rendered_html(iframe_src: str, timeout: int = 30) -> str:
    r = requests.get(iframe_src, timeout=timeout)
    r.raise_for_status()
    return r.text

def extract_notebook_inner(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#notebook") or soup.select_one("#notebook-container") or soup.body
    for s in root.select("header, nav, footer, .sharing-control-portal, .site-header-react__nav"):
        s.decompose()
    return (root.decode_contents() or "").strip()

def promote_first_heading_to_h1(md: str, fallback_title: str = "") -> str:
    lines = md.lstrip().splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s*(.*\S)\s*$", ln)
        if m:
            lines[i] = "# " + m.group(2).strip()
            return "\n".join(lines).strip()
    return (f"# {fallback_title}\n\n{md}".strip()) if fallback_title else md

def fetch_notebook_markdown(page_url: str) -> str:
    iframe_src, page_title = fetch_iframe_src(page_url)
    try:
        html = fetch_rendered_html(iframe_src)
    except requests.HTTPError:
        # フォールバック（めったに使われない想定）
        d = build_driver(headless=True)
        try:
            d.get(page_url)
            iframe = WebDriverWait(d, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#rendered-kernel-content"))
            )
            d.switch_to.frame(iframe)
            WebDriverWait(d, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#notebook")))
            time.sleep(1.0)
            root = d.find_element(By.CSS_SELECTOR, "#notebook")
            html = root.get_attribute("innerHTML") or ""
        finally:
            d.quit()

    inner = extract_notebook_inner(html)
    md = html2md(inner)
    md = promote_first_heading_to_h1(md, fallback_title=page_title)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md

def save_notebook_markdown(url: str, out_dir: str = "out/course") -> pathlib.Path:
    outp = pathlib.Path(out_dir); outp.mkdir(parents=True, exist_ok=True)
    md = fetch_notebook_markdown(url)
    path = outp / f"{normalize_slug(url)}.md"
    path.write_text(md, encoding="utf-8")
    return path

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Kaggle Notebook/Course URL")
    ap.add_argument("--out", default="out/course", help="Output directory")
    args = ap.parse_args()
    try:
        p = save_notebook_markdown(args.url, out_dir=args.out)
        print("Saved:", p)
    except Exception as e:
        print("ERROR:", repr(e), file=sys.stderr)
        sys.exit(1)
