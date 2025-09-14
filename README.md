# Kaggle Competition / Notebook Translator

Kaggle の **コンペ説明（Overview / Data / Rules）** と **Discussion 一覧**を参照し、
**Kaggle Learn コース/公開ノートブック**の本文を Markdown（英語）化、さらに **Gemini で日本語翻訳**できる Streamlit アプリです。
加えて **自分のノートブック** を Kaggle API から取得し、Markdown 化（出力含む/含まない選択）→ 翻訳まで実行できます。

---

## 特長

* **Competitions**: Overview / Data / Rules を HTML→Markdown 化 → ワンボタンで英→日翻訳
* **Discussion**: ページ送りでスレッド一覧表示
* **Notebook / Course（公開・学習コース）**: iframe レンダリングを全スクロールして本文を Markdown 抽出
* **My Notebook（自分のノートブック）**: Kaggle API で `.ipynb` を取得→Markdown 化（※出力込みも可）
* 翻訳は **Gemini（Google AI Studio / Generative Language API）** を使用

---

## リポジトリ構成（推奨）

```
kaggle-translator/
├─ app/
│  └─ app.py                          # Streamlit アプリ本体
├─ scripts/
│  ├─ save_kaggle_comp_markdown.py    # コンペ overview/data/rules → Markdown 保存
│  ├─ save_kaggle_course_markdown.py  # 公開ノート/コース → Markdown 保存（iframe 対応）
│  ├─ pull_kernel_to_markdown.py      # 自分のノートを Kaggle API で取得→Markdown
│  └─ translate_markdown_with_gemini.py # 英→日翻訳（Gemini）
├─ out/                               # 生成物（Git 管理外推奨）
├─ requirements.txt
├─ .gitignore
└─ README.md
```

> 既存の `app.py` / 各スクリプトがルート直下にある場合は、上記位置に移動してください。

---

## 必要要件

* Python **3.9+**（推奨）
* **Google Chrome / Chromium**
  `webdriver-manager` が適切な ChromeDriver を自動取得します
* **Kaggle API**（自分のノートブックを扱う場合）
* **Gemini API Key**（翻訳する場合）

---

## セットアップ

### 1) 仮想環境 & 依存インストール

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Kaggle API 設定（My Notebook 機能に必須）

1. Kaggle → 右上アイコン → **Settings** → **API** → **Create New API Token**
   `kaggle.json` がダウンロードされます。
2. 配置 & 権限設定:

   ```bash
   mkdir -p ~/.kaggle
   mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
   chmod 600 ~/.kaggle/kaggle.json
   ```
3. 動作テスト:

   ```bash
   kaggle --version
   ```

### 3) Gemini API Key（翻訳用）

* [Google AI Studio](https://aistudio.google.com/) で API キーを取得
* 環境変数に設定:

  ```bash
  export GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
  ```

  *Windows (PowerShell)*: `setx GOOGLE_API_KEY "YOUR_GEMINI_API_KEY"`

### 4)（Linux などで必要なら）追加ライブラリ

```bash
sudo apt-get update
sudo apt-get install -y libnss3 libasound2
```

---

## アプリの起動（Streamlit）

```bash
streamlit run app/app.py
```

ブラウザが開いたら、各タブから操作できます。出力はデフォルトで `out/` 配下に保存されます。

---

## 使い方（各タブ）

### Competitions

1. 「Kaggle Competition URL」に `https://www.kaggle.com/competitions/<slug>/overview`（`/data` `/rules` でも可）を入力
2. サイドバーの **「① Overview/Data/Rules を取得→翻訳（英→日）」** をクリック
3. 「Overview / Data / Rules」タブに英語・日本語の Markdown が並びます
4. 「Discussion」タブではスレッド一覧をページ送りで閲覧できます

### Notebook / Course（公開・コース）

* 例: `https://www.kaggle.com/code/ryanholbrook/a-single-neuron`
* **「② 英語MDを取得」** → **「③ 日本語に翻訳」**
* 保存先: `out/course/<slug>.md` / `out/course/<slug>.ja.md`
* 仕組み: `iframe#rendered-kernel-content` 内の `#notebook` を最下部まで自動スクロール→HTML → Markdown 変換

### My Notebook（自分のノートブック）

* 例: `https://www.kaggle.com/code/<you>/<slug>/edit`（`/edit` なし URL でもOK）
* **「④ 英語MDを取得（API）」**: Kaggle API で `.ipynb` をダウンロード→Markdown 化

  * **「出力を含める」** を ON にすると、コードセルの出力（テキスト/プロット）も Markdown に展開
* **「⑤ 日本語に翻訳」**
* 保存先: `out/kernel/<slug>.md` / `out/kernel/<slug>.ja.md`

---

## CLI での利用

### コンペの Overview/Data/Rules を保存

```bash
python3 scripts/save_kaggle_comp_markdown.py \
  --url https://www.kaggle.com/competitions/titanic \
  --out out
```

### 公開ノート／コースを保存（iframe 方式）

```bash
python3 scripts/save_kaggle_course_markdown.py \
  --url https://www.kaggle.com/code/ryanholbrook/a-single-neuron \
  --out out/course
```

### 自分のノートブックを保存（Kaggle API）

```bash
# 出力を含めない
python3 scripts/pull_kernel_to_markdown.py \
  --url https://www.kaggle.com/code/<you>/<slug>/edit \
  --out out/kernel

# 出力を含める
python3 scripts/pull_kernel_to_markdown.py \
  --url https://www.kaggle.com/code/<you>/<slug>/edit \
  --out out/kernel \
  --include-outputs
```

### Gemini で翻訳（英→日）

```bash
export GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"

# ディレクトリ内の *.md を一括翻訳（日本語は .ja.md で保存）
python3 scripts/translate_markdown_with_gemini.py \
  --in out/course \
  --glob "*.md"
```

---

## 生成物（デフォルト）

* コンペ: `out/overview.md`, `out/data.md`, `out/rules.md`（+ `.ja.md`）
* 公開/コース: `out/course/<slug>.md`（+ `.ja.md`）
* 自分のノート: `out/kernel/<slug>.md`（+ `.ja.md`）

`.ja.md` は英語 `.md` を **英→日** 翻訳したファイルです。

---

## トラブルシュート

* **Warning: Your Kaggle API key is readable …**
  → `chmod 600 ~/.kaggle/kaggle.json` を実行
* **Selenium のタイムアウト**
  ネットワークや描画遅延が原因になりがちです。再実行、待機時間延長、ヘッドレス解除（`--headless` を外す）などで改善
* **コース本文が途中までしか保存されない**
  ノートブックは IntersectionObserver による遅延描画です。保存前に最下部まで自動スクロールしていますが、回線状況で取り漏れが出る場合があります。再実行で改善することがあります
* **Gemini 翻訳が動かない**
  `GOOGLE_API_KEY` が未設定/無効の可能性。環境変数を確認してください

---

## .gitignore（例）

```
# Python
.venv/
__pycache__/
*.pyc

# App outputs
out/

# Secrets
.kaggle/
kaggle.json
.env
```

---

## セキュリティ注意

* `~/.kaggle/kaggle.json`（API キー）は **絶対に** リポジトリに含めないでください
* `GOOGLE_API_KEY` も同様に、コードに直書きせず **環境変数** で渡してください

---

## ライセンス

Aprach2
