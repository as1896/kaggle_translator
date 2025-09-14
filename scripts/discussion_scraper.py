# discussion_scraper.py
# pip install selenium webdriver-manager markdownify

import re, time, pathlib
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import markdownify


# ============ 共通ユーティリティ ============
def build_driver(headless: bool = True) -> webdriver.Chrome:
    opt = webdriver.ChromeOptions()
    if headless:
        opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument("--disable-blink-features=AutomationControlled")
    opt.add_experimental_option("excludeSwitches", ["enable-automation"])
    opt.add_experimental_option("useAutomationExtension", False)
    opt.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opt)
    try:
        drv.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
    except Exception:
        pass
    return drv


def click_cookie_if_appears(driver: webdriver.Chrome) -> None:
    for xp in [
        "//div[contains(., 'OK, Got it.') and contains(@class,'bxFwkO')]",
        "//button[contains(., 'Accept all') or contains(., 'Accept All')]",
    ]:
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp))).click()
            time.sleep(0.2)
            break
        except Exception:
            pass


def _stabilize_page(driver: webdriver.Chrome, tries: int = 6, pause: float = 0.5) -> None:
    last_h = 0
    for _ in range(tries):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        h = driver.execute_script("return document.body.scrollHeight;")
        if h == last_h:
            break
        last_h = h


def html2md(html: str) -> str:
    return markdownify.markdownify(
        html, heading_style="ATX", strip=["script", "style", "svg", "iframe"]
    ).strip()


# ============ 一覧取得（/discussion/<id> のみ・コメント行は除外） ============
# ============ 一覧取得（/discussion/<id> のみ・コメント行は除外） ============
def list_discussions(list_url: str, max_items: int = 30, page: int = 1) -> List[Dict]:
    # ページ番号に応じてURLを変える
    if page > 1:
        if "?" in list_url:
            url = f"{list_url}&page={page}"
        else:
            url = f"{list_url}?page={page}"
    else:
        url = list_url

    driver = build_driver(headless=True)
    topics: List[Dict] = []
    try:
        driver.get(url)
        click_cookie_if_appears(driver)

        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/discussion/']"))
        )
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/discussion/']")

        seen = set()
        for a in anchors:
            href = (a.get_attribute("href") or "").strip()
            if not re.search(r"/discussion/\d+/?$", href):
                continue
            if href in seen:
                continue

            title = (a.text or "").strip()
            if not title:
                try:
                    title = a.find_element(By.XPATH, ".//h3|.//span").text.strip()
                except Exception:
                    title = href.rsplit("/", 1)[-1]

            if re.fullmatch(r"comments?", title, flags=re.IGNORECASE):
                continue  # “comment(s)”のみの行は除外

            votes = comments = ""
            try:
                votes = a.find_element(By.XPATH, ".//span[contains(@class,'vote')]").text
            except Exception:
                pass
            try:
                comments = a.find_element(By.XPATH, ".//span[contains(.,'comment')]").text
            except Exception:
                pass

            topics.append({"title": title, "url": href, "votes": votes, "comments": comments})
            seen.add(href)

            if len(topics) >= max_items:
                break
    finally:
        driver.quit()
    return topics


# ============ スレッド本文取得（まず素直に取得→あとで“最初の ### まで”上を削除） ============
def _find_post_root(d: webdriver.Chrome):
    """本文ルート候補（厳しく待たずに見つかったもので進む）"""
    for xp in [
        "//main//article[.//h1 or .//h2 or .//h3]",
        "//article",
        "//main",
    ]:
        try:
            return d.find_element(By.XPATH, xp)
        except Exception:
            continue
    return None


def _first_heading_from_root(root) -> Optional[webdriver.remote.webelement.WebElement]:
    """本文ルートから最初の h1/h2/h3 を探す（header配下は除外）"""
    if root is None:
        return None
    try:
        hs = root.find_elements(By.XPATH, ".//*[self::h1 or self::h2 or self::h3][not(ancestor::header)]")
        return hs[0] if hs else None
    except Exception:
        return None


def _cut_above_first_heading(md: str) -> str:
    """
    Markdownから “最初の ### 見出し” まで上部を削除。
    ### が無ければ ##、それも無ければ # を探す。
    見つからなければそのまま返す。
    """
    for level in ("###", "##", "#"):
        m = re.search(rf"(?m)^{re.escape(level)}\s+.+$", md)
        if m:
            return md[m.start():].lstrip()
    return md.strip()

def _promote_first_heading_to_h1(md: str) -> str:
    """
    先頭から最初に現れる Markdown 見出し (#{1,6} 見出し) を必ず '# ' に統一する。
    それ以外の見出しレベルはそのまま。
    """
    lines = md.lstrip().splitlines()
    for i, line in enumerate(lines):
        m = re.match(r'^(#{1,6})\s+(.*\S)\s*$', line)
        if m:
            lines[i] = '# ' + m.group(2)
            break
    return '\n'.join(lines).strip()

def fetch_thread_markdown(thread_url: str, keep_header: bool = False) -> str:
    d = build_driver(headless=True)
    try:
        d.get(thread_url)
        click_cookie_if_appears(d)
        _stabilize_page(d)

        root = _find_post_root(d)

        if root is None:
            # 最終フォールバック：ページ全体をMD化
            base_md = html2md(d.page_source)
        else:
            # 可能なら見出し以降（タイトル要素+兄弟）をHTMLで組み立て
            heading = _first_heading_from_root(root)
            if heading is not None:
                parts = [heading.get_attribute("outerHTML")]
                for el in heading.find_elements(By.XPATH, "./following-sibling::*"):
                    h = el.get_attribute("outerHTML") or ""
                    if h.strip():
                        parts.append(h)
                body_html = "\n".join(parts)
                base_md = html2md(body_html)
            else:
                # ルート全体
                base_md = html2md(root.get_attribute("innerHTML") or "")

        md = base_md.strip()
        if not keep_header:
            md = _cut_above_first_heading(md)
        
        md = _promote_first_heading_to_h1(md)
        # 余計な連続空行を軽く整形
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return md

    finally:
        d.quit()


def save_thread_md(thread_url: str, out_dir: str = "out/discussion", keep_header: bool = False) -> pathlib.Path:
    outp = pathlib.Path(out_dir); outp.mkdir(parents=True, exist_ok=True)
    tid = thread_url.rstrip("/").split("/")[-1]
    md = fetch_thread_markdown(thread_url, keep_header=keep_header)
    path = outp / f"discussion_{tid}.md"
    path.write_text(md, encoding="utf-8")
    return path


# ============ CLI ============
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--list", help="Discussion一覧URL（例: .../discussion?sort=recent-comments）")
    ap.add_argument("--thread", help="DiscussionスレッドURL（例: .../discussion/586706）")
    ap.add_argument("--max", type=int, default=30, help="一覧取得の最大件数")
    ap.add_argument("--out", default="out/discussion", help="スレッド保存先ディレクトリ")
    ap.add_argument("--keep-header", action="store_true", help="上部を削らずそのまま出力（デバッグ用）")
    ap.add_argument("--page", type=int, default=1, help="リスト取得時のページ番号 (デフォルト=1)")
    args = ap.parse_args()

    if args.list:
        items = list_discussions(args.list, max_items=args.max, page=args.page)
        print(f"=== Page {args.page} ===")
        for i, it in enumerate(items, 1):
            print(f"{i:02d}. {it['title']} -> {it['url']}")
    elif args.thread:
        p = save_thread_md(args.thread, out_dir=args.out, keep_header=args.keep_header)
        print("Saved:", p)
    else:
        ap.print_help()
