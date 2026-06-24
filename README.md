# 諫早市 燃えないごみ → TimeTree 自動登録

諫早市（長崎県）の燃えないごみ収集日を自動でTimeTreeカレンダーに登録するシステムです。

## 仕組み

```
諫早市 PDF（年1回更新）
  ↓
GitHub Actions（毎年4月5日 自動実行）
  ↓
calendar.json / isahaya_funen.ics を GitHub Pages に公開
  ↓
iOSショートカット（毎年4月7日 自動実行）
  ↓
iOSカレンダーに「燃えないごみ」を1年分登録
  ↓
TimeTree に自動同期
```

## セットアップ

### 1. GitHub Pages を有効にする

リポジトリの Settings → Pages → Source を「GitHub Actions」に設定してください。

### 2. 初回カレンダー更新を実行する

Actions タブ → 「諫早市ごみカレンダー更新」→ 「Run workflow」

**PDFのURLについて:** 諫早市は毎年新しいPDFをアップロードします。URLが変わった場合は、
[各地域のごみの収集日程](https://www.city.isahaya.nagasaki.jp/soshiki/38/1795.html)
で最新のURLを確認し、ワークフローの「pdf_url」に入力してください。

### 3. iOSショートカットを設定する

`ios-shortcut/README.md` の手順に従ってショートカットを作成し、  
毎年4月7日に自動実行するオートメーションを設定してください。

### 4. TimeTree との連携確認

TimeTreeアプリで「設定 → カレンダー連携 → iOSカレンダー」が有効になっているか確認してください。

## ファイル構成

```
.
├── scripts/
│   ├── parse_isahaya_garbage.py   # PDFパーサー
│   └── requirements.txt
├── .github/workflows/
│   └── update_calendar.yml        # 自動更新ワークフロー
├── docs/                          # GitHub Pages で公開
│   ├── calendar.json              # iOSショートカット用
│   └── isahaya_funen.ics          # TimeTree直接購読用（オプション）
└── ios-shortcut/
    └── README.md                  # iOSショートカット作成手順
```

## PDFが解析できない場合

諫早市のPDFフォーマットが変更された場合、スクリプトが正しく解析できないことがあります。  
その場合は、PDFをダウンロードしてローカルで実行し、フォーマットを確認してください。

```bash
pip install -r scripts/requirements.txt
python scripts/parse_isahaya_garbage.py --pdf-file ダウンロードしたファイル.pdf
```
