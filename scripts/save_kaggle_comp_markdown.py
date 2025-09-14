# save_kaggle_comp_markdown.py
# Usage:
#   pip install selenium webdriver-manager markdownify
#   python3 save_kaggle_comp_markdown.py --url https://www.kaggle.com/competitions/titanic/overview
# 生成物:
#   out/overview.md, out/data.md, out/rules.md

import argparse, time, pathlib
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import markdownify

# ---- 共通: 安定する driver 構成 ----
def build_driver(headless=True):
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

def click_cookie_if_appears(driver):
    # “OK, Got it.” / “Accept all” があれば押す（無ければスルー）
    for xp in [
        "//div[contains(., 'OK, Got it.') and contains(@class,'bxFwkO')]",
        "//button[contains(., 'Accept all') or contains(., 'Accept All')]",
    ]:
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp))).click()
            time.sleep(0.3)
            break
        except Exception:
            pass

def html2md(html: str) -> str:
    return markdownify.markdownify(
        html,
        heading_style="ATX",
        strip=["script", "style", "svg", "iframe"]
    ).strip()


# ---- Overview タブ: セクションIDをピンポイント抽出 ----
def fetch_overview(driver, url) -> str:
    driver.get(url)
    click_cookie_if_appears(driver)
    # Overview ページで本文に出てくる代表的なセクションID
    sec_ids = ["abstract", "description", "evaluation", "frequently-asked-questions", "citation"]
    chunks = []
    for sid in sec_ids:
        try:
            # 1) セクションの見出しブロック出現を待つ
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, sid)))
            # 2) 直後の“本文”コンテナ（debug.html で確認できる .sc-eTCgfj）を取る
            #    先頭の1つでOK。見つからなければ、h2/p を含む最初の大きめのdivにフォールバック。
            xpaths = [
                f"//div[@id='{sid}']/following::div[contains(@class,'sc-eTCgfj')][1]",
                f"//div[@id='{sid}']/following::div[.//h2 or .//p][1]"
            ]
            el = None
            for xp in xpaths:
                try:
                    el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xp)))
                    break
                except Exception:
                    continue
            if el:
                chunks.append(el.get_attribute("innerHTML"))
        except Exception:
            # セクションが無い場合はスキップ（Overviewには全部ないこともある）
            pass
    if not chunks:
        # まれに構造が変わった場合は中央カラム全体を最後の手段で取得
        try:
            el = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//div[@data-testid='competition-detail-render-tid']//div[.//h2 and (.//p or .//li)]"
                ))
            )
            chunks.append(el.get_attribute("innerHTML"))
        except Exception:
            # デバッグ用
            pathlib.Path("debug_overview.html").write_text(driver.page_source, encoding="utf-8")
            raise RuntimeError("Overviewの本文が見つかりませんでした（debug_overview.html を確認）")
    # HTML -> Markdown
    return "\n\n---\n\n".join(html2md(c) for c in chunks)

# ---- Data / Rules はURLを変えて、中心カラムをまとめて抜く ----
def fetch_generic_tab(driver, tab_url) -> str:
    driver.get(tab_url)
    click_cookie_if_appears(driver)
    # 中央カラムの“本文に見える最初の大きな塊”を拾う（h2/p/ol/ulを含む）
    # 同様の塊が複数ある場合は上から2-3個を連結
    els = WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((
            By.XPATH,
            "//div[@data-testid='competition-detail-render-tid']"
            "//div[.//h2 or .//h3][.//p or .//li][not(ancestor::nav)][not(ancestor::aside)]"
        ))
    )
    # 取りすぎ防止で上位3ブロックに制限
    html_chunks = [e.get_attribute("innerHTML") for e in els[:3]]
    if not html_chunks:
        pathlib.Path("debug_tab.html").write_text(driver.page_source, encoding="utf-8")
        raise RuntimeError("タブ本文が見つかりませんでした（debug_tab.html を確認）")
    return "\n\n---\n\n".join(html2md(c) for c in html_chunks)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="例: https://www.kaggle.com/competitions/titanic/overview")
    ap.add_argument("--out", default="out", help="保存ディレクトリ")
    ap.add_argument("--no-headless", action="store_true")
    args = ap.parse_args()

    base = args.url.rstrip("/")
    # URL末尾をタブ名に差し替え
    def with_tab(tab):
        parts = urlparse(base)
        path = parts.path.split("/")
        if path[-1] in {"overview","data","rules"}:
            path[-1] = tab
        else:
            path.append(tab)
        return parts._replace(path="/".join(path)).geturl()

    outdir = pathlib.Path(args.out); outdir.mkdir(parents=True, exist_ok=True)

    driver = build_driver(headless=not args.no_headless)
    try:
        # Overview（セクションIDベースで精密取得）
        md = fetch_overview(driver, with_tab("overview"))
        (outdir / "overview.md").write_text(md, encoding="utf-8")
        print("✅ saved:", outdir / "overview.md")

        # Data（汎用抽出）
        md = fetch_generic_tab(driver, with_tab("data"))
        (outdir / "data.md").write_text(md, encoding="utf-8")
        print("✅ saved:", outdir / "data.md")

        # Rules（汎用抽出）
        md = fetch_generic_tab(driver, with_tab("rules"))
        (outdir / "rules.md").write_text(md, encoding="utf-8")
        print("✅ saved:", outdir / "rules.md")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
