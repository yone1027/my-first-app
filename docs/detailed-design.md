# 株価ポータル 詳細設計書(草案)

- 版: 草案 v0.4(2026-09-26)
- 変更履歴
  - v0.1 作成
  - v0.2 スプリント1の確定作業(1)。技術スタック(§2)を確定し、この Mac の実測(§2.1)と採用しなかった案(§2.2)を追記。判定ラベルの正本を `verdicts.csv` に確定し実測値に差し替え(§7.1)、売買代金の集計範囲を確定(§6.4)、`period` の既定を `13w` に、業種の太字を上位3と下位3に(§5.2・§5.6)。§12.3 を「確認してほしいこと」から「決定・反映済み」に書き換えた
  - v0.3 スプリント1の確定作業(2)。§12.2 の仮置き13件をすべて確定。土曜の処理中にスリープさせない仕組みを追加(§10.1)。キャッシュの対象を明確化し索引方式の実測値を追記(§5.5)。差分の再計算を設定に外出し(§6.2)。TradingView の URL を実機で検証(§8.7)。設定ファイルに `[aggregate]` を追加(§3.3)
  - v0.4 設定ファイルに `[theme]` を追加(§3.3)。`GET /api/theme` と設定画面 G-30 の URL を追加(§5.2・§8.1)。色は `lib/theme.ts` で CSS 変数として扱い、ハードコードしない方針にした(§8.4)
- もとにした文書
  - 基本設計書 [docs/basic-design.md](basic-design.md) v0.8
  - 要件定義書 [docs/requirements.md](requirements.md) v0.40
  - 既存の出力の実物(2026-09-26 に確認): `TechnicalAnalysis/output/screen/20260925/`、`TechnicalAnalysis/output/candidates/20260925/`、`J-Quants/output/selection/picks_20260925.*`、`J-Quants/data/raw/`、`J-Quants/data/panel/`
- 作成者: yone1027
- 状態: **草案**。基本設計書の**未決**・**仮置き**は、この文書でもそのまま書く。この文書で新しく決めた値(技術スタック・ファイルの形・API など)も、確定するまでは**仮置き**とする(§12.2 に一覧)。

この文書は、基本設計書で決めた「使う人から見た動き」を、**どう作るか**を決める。対象は、構成・技術スタック・プログラムの分け方・バッチの中身・ファイルの形・API・画面の部品・計算の手順・エラーの扱い・テストである。

**対象はスプリント1(ローカル版)**。クラウド版で変わる所は、その旨を書いて残す。

---

## 1. 設計の方針

| # | 方針 | 理由 |
|---|---|---|
| D1 | **既存の2つのプロジェクトのコードとファイルには手を入れない。** 読むだけにする。既存のスクリプトは、コマンドとして呼び出すだけにする | 要件 §6.1 |
| D2 | **分析のロジックをポータルに複製しない。** 判定・局面・指値の段・基準で落ちた理由などは、既存の出力に書かれたものをそのまま使う。ポータルが計算するのは、市場概況の集計(F1)と、表示のための簡単な計算(基本設計書 §6)だけ | 要件 §7 保守 |
| D3 | **表示の約束(R1〜R6)をデータの形でも守る。** API は合計点・総合判定・買い判定の数の列を返さない。買い判定の数は、画面の中で絞り込みのためだけに数える | 要件 §4.0 |
| D4 | **17:00ルールは集計の側で守る。** 市場概況の集計は、各週について「その週の最終営業日の17:00に使えたデータ」だけで値を作り、保存する。サーバーと画面は、保存された値をそのまま使う | 要件 R3・§5.2 |
| D5 | **期間(13・26・52週)に依存する計算はサーバーで行う。** 集計は週ごとの値(期間に依存しない値)だけを保存する | 期間を足すときに集計を作り直さずに済む |
| D6 | **スプリント1の画面と API は、クラウド版でもそのまま使える形にする。** データの読み元だけを差し替えられるように、読み込みを1か所(リーダー)にまとめる | 要件 §3.1 |

---

## 2. 技術スタック(2026-09-26 **確定**。要件定義書 §9-1 の未決を解消した)

| 層 | 使うもの | 選んだ理由 |
|---|---|---|
| サーバー | Python 3.12 + FastAPI + uvicorn | 既存の資産がすべて Python で、CSV・JSONL・npz をそのまま読める。API とファイル配信を1つのプロセスで済ませられる |
| 集計のバッチ | Python 3.12 + pandas + numpy + httpx | サーバーと同じ環境で動かす。J-Quants のキャッシュ(`.json.gz`)とパネル(`.npz`)を読む |
| Python の環境 | **`uv` が管理する Python 3.12** + ポータル専用の仮想環境 | 既存の anaconda(Python 3.9.13)に部品を足すと、既存の分析に影響するおそれがある。`uv` は自前で Python を持つので、anaconda・Homebrew のどちらにも依存しない。版をロックでき、数年後も同じ環境を作り直せる。既存のスクリプトは anaconda の Python で呼ぶ(§4.4) |
| 画面 | SvelteKit(`adapter-static` で静的な SPA に書き出す)+ TypeScript | 要件 §6.2 の候補。書き出した静的ファイルを FastAPI が配るので、動かすプロセスは1つで済む。クラウド版では静的ホスティングにそのまま載る |
| チャート | Apache ECharts | 積み上げ棒と線の重ね描き(左右2軸)、ヒートマップ、凡例での表示切り替えが1つの部品でできる。TradingView Lightweight Charts はヒートマップと積み上げ棒がないため使わない(ローソク足を描く画面はない) |
| データの保存 | ファイル(CSV・JSON)。DB は置かない | 1人で使い、書き込みは週1回のバッチだけ。データは小さい(市場概況の全履歴で数MB) |
| 常駐と定期実行 | launchd(ユーザーの LaunchAgent) | 既存の一括分析と同じ仕組み。ログイン時の自動起動と、土曜 3:00 の起動ができる |
| テスト | pytest(Python)、Vitest(画面の計算と書式) | §11 |

- Node.js は画面を書き出すときだけ使う。動かすときには要らない。

### 2.1 この Mac の実測(2026-09-26 に確認)

| 項目 | 実測 | 対応 |
|---|---|---|
| anaconda | `/Users/yone/opt/anaconda3` Python 3.9.13、pandas 1.4.4、numpy 1.21.5 | ここには何も足さない。既存のスクリプトを呼ぶときだけ使う(§4.4) |
| 既存バッチの Python | `TechnicalAnalysis/scripts/run_weekly.sh` が `PYTHON=/Users/yone/opt/anaconda3/bin/python3` と明示している | ポータルの環境を分けても既存の実行に影響しない |
| Python 3.12 | **入っていない**(あるのは anaconda 3.9.13 / Homebrew 3.14.7 / OS 標準 3.9.6) | `uv python install 3.12` で `uv` に入れさせる |
| `uv` | **入っていない** | `brew install uv` で入れる(Homebrew 7.0.6 あり) |
| Node.js | v24.21.0(nvm)、npm 11.19.0 | 画面のビルドにそのまま使える。nvm 管理なので launchd の環境からは見えないが、ビルドは手元で行うので問題ない(§10.3) |
| launchd | `com.yone.technicalanalysis.screen.plist` のみ | 同じ仕組みでポータルの2つ(常駐・週次)を足す(§10.1) |

### 2.2 採用しなかった案(2026-09-26 検討)

| 層 | 採らなかった案 | 理由 |
|---|---|---|
| Python | Homebrew の Python 3.14.7 を使う | 3.14 は出たばかりで、一部のライブラリのビルド済みパッケージが未提供のことがある。`brew upgrade` で版が上がってしまうリスクもある |
| Python | 既存の anaconda に FastAPI を足す | pandas 1.4.4 / numpy 1.21.5 のままになり、ライブラリを入れた拍子に既存の一括分析が壊れるおそれがある |
| 画面 | Vite + Svelte(SvelteKit なし) | 依存は減るが、SvelteKit の `adapter-static` はクラウド版で静的ホスティングにそのまま載せられる利点があるため、案のまま SvelteKit を採る |
| 画面 | ビルドなしの素の HTML + CDN の ECharts | npm の老朽化がない反面、977行の表の絞り込み・根拠の開閉・凡例の状態管理をすべて自分で書くことになり、コード量が増える |

---

## 3. システム構成

### 3.1 全体の図

```
┌──────────────────────── Mac ─────────────────────────────────────────────┐
│                                                                          │
│ [launchd] com.yone.technicalanalysis.screen(既存・土曜 3:00)              │
│      └─ TechnicalAnalysis/scripts/run_weekly.sh → output/screen/<日付>/   │
│                                                                          │
│ [launchd] com.yone.stockportal.weekly(新規・土曜 3:00)                    │
│      └─ 週次の後続の処理 stockportal.batch.weekly                          │
│           0. 一括分析の完了を待つ(最大3時間)                               │
│           1. TechnicalAnalysis/scripts/candidates.py  → output/candidates/ │
│           2. J-Quants/scripts/weekly_picks.py         → output/selection/  │
│           3. 市場概況の集計 stockportal.batch.aggregate                    │
│                 ├ 読む: J-Quants/data/raw/(株価・銘柄一覧・TOPIX・          │
│                 │        取引カレンダー・決算短信)                          │
│                 ├ 取る: J-Quants 投資部門別、財務省、日本銀行、EIA         │
│                 └ 書く: /Users/yone/StockPortal/data/market/               │
│           → 実行状況: /Users/yone/StockPortal/data/status/                 │
│                                                                          │
│ [launchd] com.yone.stockportal.server(新規・ログイン時に起動、落ちたら再起動)│
│      └─ uvicorn stockportal.app(0.0.0.0:8765)                            │
│           ├ /api/*  上の出力を読んで JSON を返す(読むだけ)                  │
│           └ /*      画面(SvelteKit の書き出し)                              │
└──────────────────────────────────────────────────────────────────────────┘
        ↑ http://localhost:8765            ↑ http://<Mac の名前>.local:8765
      Mac のブラウザ                     同じ家の Wi-Fi のスマホ
```

- ポートは **8765**(2026-09-26 確定)。実測で未使用を確認した。他プロセスの待ち受け(AirPlay の 5000・7000、Orca の 6768)とも衝突しない。

### 3.2 置き場所

| 置き場所 | 中身 | git で管理 |
|---|---|---|
| このリポジトリ(`my-first-app/`) | サーバー・バッチ・画面のコード、launchd の雛形、設定の見本 | する |
| `/Users/yone/StockPortal/` | 動かすための設定、秘密情報、集計の結果、実行状況、ログ | しない |
| `/Users/yone/J-Quants/`、`/Users/yone/TechnicalAnalysis/` | 既存のプロジェクト(読むだけ) | しない(要件 §8) |

#### リポジトリの中

```
my-first-app/
├─ docs/                       要件定義書・基本設計書・この文書
├─ server/
│  ├─ pyproject.toml
│  ├─ stockportal/
│  │  ├─ app.py                FastAPI の組み立て(ルーター・ミドルウェア・画面の配信)
│  │  ├─ config.py             設定ファイルの読み込み(§3.3)
│  │  ├─ security.py           接続元の制限(§9.1)
│  │  ├─ api/                  market.py / weekly.py / search.py / status.py
│  │  ├─ readers/              ファイルを読んで内部の形にする(§7)
│  │  │    screen.py / picks.py / candidates.py / market.py / calendar.py / status.py
│  │  ├─ calc/                 期間に依存する計算(§5.6)
│  │  └─ batch/
│  │       ├─ weekly.py        週次の後続の処理(§4)
│  │       └─ aggregate/       市場概況の集計(§6)
│  │            __main__.py / weeks.py / turnover.py / topix.py / valuation.py
│  │            investor.py / indicators.py / sources/(jquants.py, mof.py, boj.py, eia.py)
│  └─ tests/
├─ web/                        SvelteKit(§8)
│  └─ src/ routes/ lib/
├─ deploy/
│  ├─ launchd/                 com.yone.stockportal.server.plist / com.yone.stockportal.weekly.plist
│  └─ install.sh               仮想環境の作成、画面の書き出し、plist の配置と読み込み
└─ config/config.example.toml
```

#### `/Users/yone/StockPortal/`(リポジトリの外)

```
StockPortal/
├─ config.toml                 設定(§3.3)
├─ .env                        EIA などの API キー(J-Quants のキーは置かない)
├─ app/                        リポジトリの動かす版(install.sh が置く。§10.3)
├─ data/
│  ├─ market/                  市場概況の集計の結果(§6.9)
│  ├─ raw/                     集計が新しく取るデータのキャッシュ(投資部門別・財務省・日本銀行・EIA)
│  └─ status/                  週次の後続の処理の実行状況(§4.6)
└─ logs/                       サーバーとバッチのログ(§10.2)
```

### 3.3 設定ファイル(`/Users/yone/StockPortal/config.toml`)

コードにパスを直接書かない(要件 §6.1)。見本は `config/config.example.toml`。

```toml
[server]
host = "0.0.0.0"
port = 8765
allowed_hosts = ["localhost", "127.0.0.1", "stockportal.local"]   # Host ヘッダーで受け付ける名前(§9.1)

[paths]
screen_dir     = "/Users/yone/TechnicalAnalysis/output/screen"
candidates_dir = "/Users/yone/TechnicalAnalysis/output/candidates"
selection_dir  = "/Users/yone/J-Quants/output/selection"
jquants_raw    = "/Users/yone/J-Quants/data/raw"
jquants_env    = "/Users/yone/J-Quants/.env"
portal_data    = "/Users/yone/StockPortal/data"
logs           = "/Users/yone/StockPortal/logs"

[batch]
python_existing = "/Users/yone/opt/anaconda3/bin/python3"   # 既存のスクリプトを呼ぶ Python
wait_screen_max_minutes = 180
wait_screen_poll_seconds = 60
step_timeout_minutes = { candidates = 120, weekly_picks = 180, aggregate = 60 }

[aggregate]
exclude_markets = ["0105", "0109"]   # 集計から外す市場区分。TOKYO PRO MARKET と ETF・REIT など(§6.4)
recompute_weeks = 4                  # 毎週さかのぼって作り直す週数(§6.2)

[theme]
# 色の既定値(基本設計書 §4.8)。端末ごとの上書きは設定画面 G-30(localStorage)で行う。
bg           = "#F5F3EE"
surface      = "#FFFFFF"
surface_alt  = "#F7F5F0"
text         = "#1C1B19"
text_sub     = "#57534A"
text_muted   = "#6B675E"
border       = "#E4E1D8"
border_strong = "#D6D2C7"
font_family  = '"BIZ UDPGothic", sans-serif'
# 判定のラベル(背景/文字の組)
buy_bg      = "#F7E3DC"
buy_fg      = "#B1442A"
sell_bg     = "#DFE9F2"
sell_fg     = "#2F6690"
neutral_bg  = "#EEECE6"
neutral_fg  = "#57534A"
unknown_bg  = "#FFFFFF"
unknown_fg  = "#6B675E"
conflict_bg = "#F0E4EE"
conflict_fg = "#7A4B72"
# チャートの面(文字ではないので画面案の値のまま)
up   = "#B5452B"
down = "#2F6690"
# 市場区分
prime    = "#2E4057"
standard = "#3E8E7E"
growth   = "#9A5B8F"
# 主体(海外投資家・個人・投資信託・事業法人・信託銀行・証券会社の自己売買)
investors = ["#2E4057", "#E0912F", "#3E8E7E", "#9A5B8F", "#8DB3D9", "#C9B37E"]

[schedule]
delayed_after = "SAT 12:00"     # これを過ぎても前の週のままなら「更新が遅れています」(基本設計書 §4.3)

[api]
jquants_per_minute = 100
jquants_fins_per_minute = 60
```

---

## 4. 週次の後続の処理(`stockportal.batch.weekly`)

### 4.1 処理の流れ

```
起動(土曜 3:00、launchd。caffeinate -i -m -s で包む。§10.1)
 │
 ├─ 基準日を決める(§4.2)
 ├─ 二重起動を防ぐ(ロックファイル data/status/weekly.lock。あれば終わる)
 ├─ 一括分析の完了を待つ(§4.3)
 │     └ 3時間待ってもそろわない → 手順1・2は「skipped」、手順3だけ動かす
 ├─ 手順1 candidates.py   ─┐
 ├─ 手順2 weekly_picks.py ─┼─ 前の手順が失敗しても、次の手順は動かす(要件 §6.1)
 ├─ 手順3 市場概況の集計   ─┘
 └─ 実行状況を書く(§4.6)。ロックファイルを消す
```

- 手順3 は、手順2 が更新した株価のキャッシュを使う(要件 §6.1)。手順2 が失敗したときも手順3 は動かし、キャッシュにある週までを集計する。その週が右端に来ないときは、画面の「更新が遅れています」で分かる(§5.7)。

### 4.2 基準日の決め方
- J-Quants の取引カレンダーのキャッシュ(§6.1)から、「今日を含めず、最終営業日の 17:00 を過ぎた、いちばん新しい週の最終営業日」を基準日とする。
  - 土曜 3:00 に動かせば、通常はその週の金曜。祝日の週は木曜など。
- 手順1・2 には、この基準日を `--as-of` で渡す。既存のスクリプトが自分で決める基準日と食い違わないようにするため。
- 手動で動かすときは `--as-of YYYY-MM-DD` で指定できる(§4.7)。

### 4.3 一括分析の完了の待ち方
- `screen_dir/<基準日 YYYYMMDD>/` に `verdicts.csv` と `report.md` の**両方**がそろったら、完了とみなす(要件 §6.1)。
- 60秒ごとに確かめる。最大180分待つ(設定 `wait_screen_*`)。
- 一括分析と同じ 3:00 に起動するので、最初の約40分は待つことになる。

### 4.4 各手順の呼び出し

| 手順 | コマンド(作業フォルダ) | Python | 時間の上限 | 成功の条件 |
|---|---|---|---|---|
| 1 | `scripts/candidates.py --as-of <基準日>`(`/Users/yone/TechnicalAnalysis`) | 既存の anaconda | 120分 | 終了コード 0 かつ `candidates/<YYYYMMDD>/candidates.csv` がある |
| 2 | `scripts/weekly_picks.py --as-of <基準日>`(`/Users/yone/J-Quants`) | 既存の anaconda | 180分 | 終了コード 0 かつ `selection/picks_<YYYYMMDD>.md` がある |
| 3 | `python -m stockportal.batch.aggregate --as-of <基準日>`(`/Users/yone/StockPortal/app/server`) | ポータルの仮想環境 | 60分 | 終了コード 0 かつ `data/market/manifest.json` の `latest_week_end` が基準日 |

- 手順1・2 は `subprocess.run` で呼び、標準出力とエラーを、そのまま手順ごとのログに書く(§10.2)。
- 時間の上限を超えたら、そのプロセスを止めて「timeout」とする。
- 手順2 のログは、既存の約束どおり J-Quants 側にも出る(`output/logs/weekly_<基準日>.log`)。ポータルはそれを消したり動かしたりしない。

### 4.5 launchd の設定(`com.yone.stockportal.weekly.plist`)
- `StartCalendarInterval`: `Weekday=6, Hour=3, Minute=0`(土曜 3:00)。
- `ProgramArguments`: ポータルの仮想環境の Python で `-m stockportal.batch.weekly`。
- Mac がスリープしていて 3:00 を逃したときは、launchd の仕組みで、起きたときに1回動く。そのときも手順は同じ(基準日は §4.2 で決まるので、遅れても結果は変わらない)。

### 4.6 実行状況の記録(`data/status/weekly_<YYYYMMDD>.json`)

```json
{
  "as_of": "2026-09-25",
  "started_at": "2026-09-26T03:00:02+09:00",
  "finished_at": "2026-09-26T04:52:10+09:00",
  "screen_ready_at": "2026-09-26T03:38:40+09:00",
  "steps": [
    {"name": "candidates",   "status": "ok",      "started_at": "…", "finished_at": "…", "exit_code": 0, "log": "logs/weekly/20260925_candidates.log"},
    {"name": "weekly_picks", "status": "failed",  "started_at": "…", "finished_at": "…", "exit_code": 1, "log": "…"},
    {"name": "aggregate",    "status": "ok",      "started_at": "…", "finished_at": "…", "exit_code": 0, "log": "…"}
  ]
}
```

- `status` は `ok` / `failed` / `timeout` / `skipped` / `running`。
- 手順を始めるたびに書き直す(途中で止まっても、どこまで進んだか分かるようにする)。書くときは、一時ファイルに書いてから名前を変える(§6.10)。
- サーバーは、この記録を「最終更新」と「更新が遅れています」の表示に使う(§5.7)。

### 4.7 手動での実行
- `python -m stockportal.batch.weekly --as-of 2026-09-25 [--only aggregate] [--no-wait]`
  - `--only`: 指定した手順だけ動かす(やり直し用)。
  - `--no-wait`: 一括分析の完了を待たない。
- 市場概況の集計だけを、過去の全週について作り直す: `python -m stockportal.batch.aggregate --rebuild`。初めて動かすときも、これを使う。

---

## 5. サーバー(API)

### 5.1 組み立て
- `app.py` で次を組み立てる。
  1. 接続元の制限のミドルウェア(§9.1)
  2. API のルーター(`/api/...`)。受け付けるのは `GET` だけ
  3. 画面の配信。`web/build/` の静的ファイルを配る。どのファイルにも当たらない URL には `index.html` を返す(画面の側で URL を解釈する。§8.1)
- 応答は gzip で圧縮する(FastAPI の `GZipMiddleware`。1KB 以上)。
- すべての応答に `X-Robots-Tag: noindex` を付ける(クラウド版の準備。基本設計書 §9)。

### 5.2 API の一覧

| API | 使う画面 | 中身 |
|---|---|---|
| `GET /api/status` | 全画面(ヘッダー) | データの時点・最終更新・遅れ(§5.7) |
| `GET /api/market/japan?period=13w` | G-11 | 売買代金のカード、TOPIX と売買代金の週足、配分、主体別(東証全体)、EPS・PER、指標 |
| `GET /api/market/segments?period=13w` | G-12 | 区分ごとのシェアと PER、主体別(区分ごと) |
| `GET /api/market/sectors?period=13w&scope=all` | G-13 | 業種の一覧とヒートマップ |
| `GET /api/weekly/dates` | G-21〜G-23 | 基準日の一覧と、その週にそろっているデータ |
| `GET /api/weekly/{date}/verdicts` | G-21 | 判定表の全行、絞り込みの選択肢、失敗した銘柄 |
| `GET /api/weekly/{date}/verdicts/{code}` | G-21(根拠) | その銘柄の手法ごとの結果(シグナル・根拠・注意) |
| `GET /api/weekly/{date}/picks` | G-22 | 注文の前提、候補、指値の段、参考、検証の限界 |
| `GET /api/weekly/{date}/candidates` | G-23 | 買い候補の全行 |
| `GET /api/search?q=...` | ヘッダー | 銘柄の候補(最大10件) |
| `GET /api/theme` | 全画面 | `config.toml` の `[theme]`(色と書体。基本設計書 §4.8) |
| `GET /api/health` | (見張り用) | `{"ok": true}` |

- `period` は `13w` / `26w` / `52w`(**既定 `13w`**。2026-09-26 確定)。`scope` は `all` / `prime` / `standard` / `growth`(既定 `all`)。`date` は `YYYY-MM-DD` か `latest`(既定 `latest`)。
- パラメータが不正なときは、既定値に置き換えて返す(基本設計書 §3.1)。応答の `params` に、実際に使った値を入れる。画面はそれで URL を直す。
- 数値は、丸めずに返す。書式(丸め・3桁区切り・符号)は画面の側で行う(§8.5)。値がないときは `null`。

### 5.3 市場概況の API の応答(抜粋)

`GET /api/market/japan?period=52w`

```jsonc
{
  "params": {"period": "52w", "weeks": 52, "recent": 8},
  "as_of_week": {"start": "2026-09-21", "end": "2026-09-25"},
  "weeks": [ {"start": "2025-09-29", "end": "2025-10-03", "days": 5, "short": false}, … ],   // 52件
  "turnover": {
    "latest": 3.37e13, "avg13": 3.04e13, "ratio13": 1.11, "percentile": 71,
    "series": [3.1e13, …], "ma13": [2.9e13, …]
  },
  "topix": {"close": [...], "ma13": [...], "ma26": [...], "ma52": [...]},
  "allocation": [ {"segment": "prime", "share_latest": 81.2, "share_change_pt": -0.8}, … ],
  "investors": {
    "section": "all", "latest_published": {"start": "2026-09-14", "end": "2026-09-18", "pub_date": "2026-09-25"},
    "subjects": [
      {"key": "foreigners", "series": [1.2e11, …, null], "total": 1.52e12, "avg_recent": …, "avg_period": …}, …
    ],
    "summary": {"up": ["foreigners", "trust_banks"], "down": ["individuals"]}
  },
  "valuation": {"per": [...], "eps": [...], "n_target": 3512, "n_excluded_loss": 214,
                "per_change": 1.3, "eps_change_pct": 3.1, "topix_change_pct": 8.2, "per_change_pct": 5.0},
  "indicators": [ {"key": "jgb10y", "values": [...], "latest": 1.62, "change": 17, "unit": "bp", "last_obs": "2026-09-25"}, … ]
}
```

- `series` などの配列は、`weeks` と同じ並び・同じ長さにする。未公表の週やデータのない週は `null`。
- 主体ごとの週の値(`subjects[].series`)は、6つとも返す。主体を選んで積み上げ直すのは画面の中で行う(§8.4)。
- `summary` は、6つとも表示しているときの要約。主体を外しても要約は変えない(2026-09-26 確定)。凡例で主体を外すのは見やすさのための操作なので、要約(事実の記述)は変えない。

### 5.4 週次の分析結果の API の応答(抜粋)

`GET /api/weekly/2026-09-25/verdicts`

```jsonc
{
  "date": "2026-09-25",
  "methods": [                                    // 並び順は §7.1 の表のとおり(固定)
    {"key": "granville", "label": "グランビル", "timeframe": "週足"}, …
  ],
  "universe_count": 977,
  "rows": [
    {"code": "8306", "name": "三菱ＵＦＪフィナンシャル・グループ", "market": "prime", "s33": "7050",
     "market_cap_oku": 440767,
     "v": {"granville": ["buy", "買い③"], "earnings-breakout": ["neutral", "…"], "flag-pennant": ["conflict", "…"], … }}
  ],
  "failed": [ {"code": "…", "name": "…", "reason": "…"} ]
}
```

- 判定は `buy` / `neutral` / `sell` / `unknown` / `conflict` の5つの記号で返す。画面で日本語のラベルにする。
- 全行(約1,000行、gzip で約60KB)を1回で返す。絞り込み・並べ替え・ページ送りは画面の中で行う(§8.6)。
- 買い判定の数・合計点の項目は**返さない**(D3)。

`GET /api/weekly/2026-09-25/verdicts/8306`

```jsonc
{
  "code": "8306",
  "methods": {
    "granville": {"verdict": "buy", "phase_label": "買い③(…)", "timeframe": "weekly",
                  "premise": "週足・13週線・判定に使う範囲は直近8本",
                  "signals": [ {"date": "2026-09-18", "direction": "buy", "name": "…", "basis": "…", "provisional": true,
                                "evidence": [ {"label": "…", "date": "…", "values": {"C": 3714.0}} ] } ],
                  "notes": ["…"]},
    "flag-pennant": {"flag": {…}, "pennant": {…}}          // 2つの結果をそのまま並べる(§7.2)
  }
}
```

### 5.5 ファイルの読み込みとキャッシュ
- リーダー(`readers/`)は、読んだ結果をメモリに持つ。キーは「ファイルのパスと更新時刻(mtime)とサイズ」。どれかが変わったら読み直す。
  - バッチがファイルを書き換えても、サーバーを再起動せずに新しい値を返せる。
- `results.jsonl`(1週あたり16〜30MB)は、全部をメモリに持たない。最初に1回読み、銘柄コード → **最後の行**のファイル内の位置(バイト)の索引だけを作る(要件 §5.3)。根拠の API では、その位置から1行だけ読む。
  - 実測(2026-09-26。`screen/20260925/results.jsonl` 15.9MB・977銘柄): 全件を辞書に載せると **49MB** 消費するが、索引だけならメモリは実質ゼロで、1銘柄の取り出しは **0.2ミリ秒**。索引の作成は 0.1 秒未満。
- 市場概況の集計の結果(§6.9)は、全部を読んで pandas の表で持つ(全履歴でも数MB)。
- キャッシュは、ファイルごとに最新の1つだけを持つ。基準日を切り替えて過去の週を見たときは、直近の**8週分**まで持つ(LRU。2026-09-26 確定)。
  - 8週分を持つ対象は、**小さいファイルと索引だけ**にする。`verdicts.csv`(1週約290KB)・`report.md`・`universe.csv`・`candidates.csv`・`picks_*.md` と、`results.jsonl` の索引。8週分で合計3MB程度に収まる。
  - `results.jsonl` の**中身**は、どの週についてもメモリに載せない(上の索引方式)。8週分を辞書に載せると約400MB になるため。

### 5.6 期間に依存する計算(`calc/`)
基本設計書 §6 の式を、次の手順で計算する。

1. 集計の結果から、最新の確定した週を右端に、N 週(N = 13・26・52)を切り出す。移動平均線は、集計の側で全履歴から計算済みのものを使う(期間より前の週も使う。基本設計書 §5.1 (3))。
2. R = 2・4・8 として、直近 R 週と期間 N 週の平均を取る。
3. データのない週(`null`)は、平均・合計から外す(基本設計書 §4.10「ある週だけで計算する」)。
4. 期間の中での位置(パーセンタイル)は、`round(100 × (直近の週以下の週の数) ÷ (値のある週の数))`。
5. 期間の変化(EPS・PER・指標)は、期間の最初と最後の「値のある週」どうしで計算する。

6. 業種の太字の対象は、期間平均比の**上位3と下位3**(2026-09-26 確定。基本設計書 §5.3)。応答では業種ごとに `emphasis: "top" | "bottom" | null` を付けて返し、画面は閾値を持たない。
   - 固定の閾値(当初の仮置きは12%)は使わない。期間が長いほどシェアの振れ幅が広がるため、1つの値では3つの期間に共通して使えない。実測(直近12週 × 33業種)では |期間平均比| の中央値が 13週 13.2%・26週 16.3%・52週 24.6% で、12% 以上になる業種は 13週 18.2・26週 20.8・52週 28.1(33業種中)だった。

- ここで作った値だけを返す。丸めない。

### 5.7 データの時点と「更新が遅れています」(`GET /api/status`)

```jsonc
{
  "now": "2026-09-26T13:05:00+09:00",
  "expected_week_end": "2026-09-25",
  "market": {"data_week_end": "2026-09-25", "last_updated": "2026-09-26T04:52:10+09:00", "delayed": false},
  "weekly": {"latest_date": "2026-09-25", "last_updated": "2026-09-26T04:10:31+09:00", "delayed": false,
             "steps": {"screen": "ok", "candidates": "ok", "weekly_picks": "failed", "aggregate": "ok"}}
}
```

| 項目 | 決め方 |
|---|---|
| `expected_week_end` | 取引カレンダーで、今の時刻より前に最終営業日の17:00を過ぎた、いちばん新しい週の最終営業日 |
| `market.data_week_end` | `manifest.json` の `latest_week_end` |
| `market.last_updated` | `manifest.json` の `generated_at` |
| `weekly.latest_date` | 基準日の一覧(§7.1)のいちばん新しい日 |
| `weekly.last_updated` | その基準日の `verdicts.csv`・`picks_*.csv`・`candidates.csv` の更新時刻のうち、いちばん新しいもの |
| `delayed` | 今が「`expected_week_end` の週の土曜 12:00」(設定 `delayed_after`)を過ぎていて、データの週が `expected_week_end` より古い。または、実行状況(§4.6)でその画面の元になる手順が `failed` / `timeout` |

- 画面は、この API をページを開くたびに1回呼ぶ。自動では呼び直さない(基本設計書 §7.1)。

### 5.8 銘柄の検索(`GET /api/search`)
- 検索の対象: 最新の銘柄一覧(`jquants_raw/equities__master/` のいちばん新しい `date=*.json.gz`)。ETF・REIT(`0109`)、TOKYO PRO MARKET(`0105`)は除く。
- 一括分析の対象かどうか: 最新の基準日の `universe.csv` に載っているか。
- 照合の手順
  1. 入力と銘柄名を、どちらも NFKC で正規化し、英字は大文字にする(`Ｓａｎｓａｎ` と `Sansan` が一致するように)。
  2. 入力が4〜5文字の英数字なら、コードの前方一致を先に並べる。コードは5桁の末尾の `0` を落とした4桁で比べる(`287A0` → `287A`)。
  3. 次に、銘柄名の部分一致。一致した位置が前の方ほど上に並べる。
  4. 最大10件。
- 応答: `[{"code": "287A", "name": "…", "market": "growth", "in_universe": false}]`。

### 5.9 エラーの応答

| 状況 | HTTP | 本文 | 画面の動き |
|---|---|---|---|
| その基準日のフォルダ・ファイルがない | 404 | `{"error": "no_data", "detail": "picks"}` | そのタブに「この週のデータはありません」 |
| 存在しない基準日 | 404 | `{"error": "no_such_date", "latest": "2026-09-25"}` | 最新の基準日で開き直し、「指定した基準日のデータはありません」 |
| 市場概況の集計の結果がない | 503 | `{"error": "not_built"}` | 各カードに「データを読み込めませんでした」 |
| ファイルの形が想定と違う(列がない等) | 500 | `{"error": "bad_format", "file": "…"}` | 同上。ログに列名などを書く |
| 存在しない API | 404 | `{"error": "not_found"}` | — |
| 家の外からの接続 | 403 | 本文なし | 画面は出ない(§9.1) |

- 例外はすべて1か所(例外ハンドラー)で受け、スタックトレースは応答に入れず、ログにだけ書く。

---

## 6. 市場概況の集計(`stockportal.batch.aggregate`)

### 6.1 入力

| データ | 読む場所 | 形 |
|---|---|---|
| 株価四本値(全銘柄。`Va`・`MktCap`) | `jquants_raw/equities__bars__daily/date=YYYY-MM-DD.json.gz` | `{"fetched_at", "path", "params", "data": [{Date, Code, …, Va, MktCap, …}]}` |
| 上場銘柄一覧(区分 `Mkt`/`MktNm`、`S33`) | `jquants_raw/equities__master/date=YYYY-MM-DD.json.gz` | 同上。**週に1回程度**の日付で保存されている(2016-11 から 884 件) |
| TOPIX | `jquants_raw/indices__bars__daily__topix/` のうち `to=` がいちばん新しいファイル | `data: [{Date, O, H, L, C}]` |
| 取引カレンダー | `jquants_raw/markets__calendar/` のうち `to=` がいちばん新しいファイル | `data: [{Date, HolDiv}]` |
| 決算短信 | `jquants_raw/fins__summary/date=YYYY-MM-DD.json.gz` | `data: [{DiscDate, DiscTime, Code, DocType, CurPerType, FNP, NxFNp, …}]` |
| 投資部門別情報 | J-Quants `/equities/investor-types` を**集計が取る**。キャッシュは `portal_data/raw/investor_types/` | §6.7 |
| 国債利回り(10年) | 財務省 `jgbcm_all.csv`(履歴)・`jgbcm.csv`(当月)を取る。キャッシュは `portal_data/raw/mof/` | §6.8 |
| ドル円(17時・中値) | 日本銀行 時系列統計 API を取る。キャッシュは `portal_data/raw/boj/` | §6.8 |
| WTI スポット | EIA Open Data API v2 を取る。キャッシュは `portal_data/raw/eia/` | §6.8 |

- J-Quants のキャッシュは**読むだけ**。足りない日付があっても、集計は J-Quants の株価を取りに行かない(取るのは手順2 の `weekly_picks.py` の役目。D1)。足りない日は、その日がない週として扱い、ログに警告を書く。
- 銘柄一覧は、各日について「その日以前でいちばん近い日付の一覧」を使う(基本設計書 §6.4)。17:00ルールに照らしても、過去の日付の一覧は、その日に使えたものである。
- API キー: J-Quants は `jquants_env`(既存の `.env`)の `JQUANTS_API_KEY` を読む。EIA は `/Users/yone/StockPortal/.env` の `EIA_API_KEY`。キーはログに書かない。

### 6.2 処理の手順

```
1. 取引カレンダーから週の一覧を作る(weeks.csv)                     §6.3
2. 新しく取るデータを取る(投資部門別・財務省・日本銀行・EIA)          §6.7, §6.8
   └ 取れなかったものは、前回のキャッシュで続ける。manifest に記録する
3. 週ごとの売買代金を、全体・区分・業種ごとに合計する(turnover.csv)   §6.4
4. TOPIX の週の終値と移動平均線(topix.csv)                          §6.5
5. EPS・PER(valuation.csv)                                          §6.6
6. 主体別売買動向(investors.csv)                                    §6.7
7. 指標(indicators.csv)                                             §6.8
8. manifest.json を書き、一時フォルダを本番のフォルダに入れ替える       §6.9, §6.10
```

- 普段(土曜の実行)は、**差分だけ**計算する。前回の結果を読み、最後の **4週**(設定 `[aggregate] recompute_weeks`)を計算し直して、それより新しい週を足す(2026-09-26 確定)。
  - さかのぼって作り直す理由は、すでに集計した週の値が後から変わることがあるため。(1) 主体別売買動向は対象週の翌週に公表される(1週遅れ。要件 F1-9)。(2) F1-7 の3つの指標は公表が不定期に遅れる。(3) J-Quants のキャッシュが後から直ることがある。
  - **4週は実測に基づく数字ではない。** (1) の1週遅れには2週で足りるが、(2)(3) には上限がないため余裕を見た値である。キャッシュのファイル更新時刻から訂正の幅を測ろうとしたが、10年分を一括取得した跡と区別できなかった(2026-09-26 に確認)。
  - 設定で変えられるようにしておき、実運用で足りないと分かったときはコードを直さずに増やす。
- `--rebuild` のときは、キャッシュにある最も古い週(2016-09 ごろ)から全部を計算する。

### 6.3 週の作り方(`weeks.csv`)
- 週は、月曜〜日曜の暦の週で区切り、その中の営業日(`HolDiv` が `1` または `2`)を、その週の営業日とする。
  - `HolDiv=2` は半日立会。営業日に数える(基本設計書 §6.5)。
- `week_end` = その週の最終営業日。`days` = 営業日の数。`short` = `days < 5`。
- 確定: その週の `week_end` の 17:00(JST)を過ぎていれば確定。集計は確定した週だけを出力する(基本設計書 §6.1)。
- 営業日が1日もない週(年末年始など)は作らない。

### 6.4 売買代金(`turnover.csv`)
- 各営業日の株価四本値から、`Va`(円)を銘柄ごとに取る。
- その日の銘柄一覧(§6.1)で、銘柄ごとに区分と S33 業種を付ける。
- **集計の対象から外す銘柄**(2026-09-26 **確定**。要件定義書 §9-8 を解消した)
  - `Mkt` が `0109`(ETF・REIT など)、`0105`(TOKYO PRO MARKET)の銘柄。既存のパネル(`J-Quants/swing/panel.py` の `EXCLUDED_MARKETS`)と同じ範囲にする。
  - 銘柄一覧に載っていない銘柄(ログに件数を書く)
  - 外す区分の一覧は設定(`[aggregate] exclude_markets`)に書き、あとから設定だけで変えられるようにする(既定は `["0105", "0109"]`)。
  - 実測(2026-09-26。直近260営業日を5日おきにサンプル、計 449 兆円): `0109` は全体の **5.19%**(月ごとに 3.70%〜6.87%)、`0105` は **0.00003%**。`0109` の 545 銘柄はすべて業種コードが `9999`(その他)で業種の段に落ちず、売買代金の上位は 1570 NEXT FUNDS 日経レバレッジ指数(単独で全体の 1.47%)など指数連動・レバレッジ型の ETF である。業種への資金の移動を見る画面(F1-6)の趣旨に合わないため外す。判定表(F2)と母集団が揃う利点もある。
- **東証が公表する売買代金には一致させない**(2026-09-26 確定)。J-Quants の銘柄ごとの `Va` の合計をそのまま使う。F1-6 で見るのは金額そのものではなくシェア(割合)なので、絶対値が公表値とずれていても差し支えない。画面には「集計の範囲」の注記を出す(基本設計書 §5.1)。
- 週・区分・業種ごとに `Va` を合計する。出力する組み合わせは次のとおり。

| `scope` | `s33` | 意味 |
|---|---|---|
| `all` | `ALL` | 全体(G-11 の売買代金) |
| `prime` / `standard` / `growth` | `ALL` | 区分の合計(G-11 の配分、G-12) |
| `all` | 業種コード | 全市場の業種(G-13 の「全市場」) |
| `prime` / `standard` / `growth` | 業種コード | 区分の中の業種(G-13 で区分を選んだとき) |

- 区分の対応(`Mkt` → `scope`): `0111` → `prime`、`0112` → `standard`、`0113` → `growth`。
- **2022年4月の市場再編より前の区分**(東証1部・2部・マザーズ・JASDAQ)は、`scope` に `legacy_1st` などの別の値で保存し、新区分には読み替えない。画面での並べ方は**未決**(基本設計書 §10.4-6)。決まるまでは、G-11・G-12 の区分の表示は、新区分がある週(2022-04-04 の週から)だけを描く(**仮置き**)。
  - 旧区分のコードの一覧は**要確認**(銘柄一覧のキャッシュの 2022-03 以前から拾う)。

### 6.5 TOPIX(`topix.csv`)
- 週の終値 = その週の最終営業日の `C`。
- 13週線・26週線・52週線 = 週の終値の単純移動平均。その週を含む直近 k 週。k 週そろわない週は `null`。
- 全履歴で計算して保存する(期間より前の週を使うため)。

### 6.6 EPS・PER(`valuation.csv`)

**各週について、各銘柄の「その週の時点で最新の会社予想の当期純利益」を決める**

1. 決算短信を、開示の日時 `DiscDate` + `DiscTime`(JST)の順に並べる。
2. その週の `week_end` の 17:00 までに開示されたもののうち、銘柄ごとに最後の1件を採る(17:00ルール。要件 F1-8)。
3. その1件から、使う予想の値を次で決める。
   - `DocType` が **`FYFinancialStatements_*`(本決算)のとき: 翌期の予想 `NxFNp`**。
   - それ以外(四半期の決算、予想の修正): 当期の予想 `FNP`。
   - 値が空のときは、その銘柄の予想はないものとする。
   - **注意**: 翌期の予想の項目名は **`NxFNp`**(小文字の p)である。キャッシュの実物で確認した(2026-09-26)。当初 `NxFNP` と書いていた要件定義書 F1-8 も実物に合わせて直した(§12.3)。
   - **`CurPerType` ではなく `DocType` で見分ける(2026-09-26 確認・修正)。** 当初は「`CurPerType` が `FY`」としていたが、実物では `EarnForecastRevision`(予想の修正)にも `CurPerType` が `FY` のものがあり、その場合に入っているのは**当期**の予想 `FNP` である。直近60ファイルを数えた結果は次のとおり。

| `DocType` | 件数 | `FNP` 有 | `NxFNp` 有 |
|---|---|---|---|
| `1Q/2Q/3QFinancialStatements_*` | 3,570 | 3,362 | 0 |
| `FYFinancialStatements_*` | 418 | 0 | 374 |
| `EarnForecastRevision` | 325 | 209 | 0 |
| `DividendForecastRevision`・`REITEarnForecastRevision` | 108 | 0 | 0 |

   - 配当だけの修正(`DividendForecastRevision`・`REITEarnForecastRevision`)は、どちらの項目も空なので読み飛ばす。
4. 予想の値が 0 より大きい銘柄を**対象**、0 以下を**除いた赤字予想**、予想がない銘柄は数えない。

**合計する**
- 時価総額 = その週の最終営業日の `MktCap`。
  - **`MktCap` の単位は百万円(2026-09-26 確定)。** `verdicts.csv` の「時価総額(億円)」と6銘柄で突き合わせ、`MktCap ÷ 100 = 億円` が比 1.0000 で一致した。`FNP`・`NxFNp` は**円**の文字列(例: 平和堂 `'9800000000'` = 98億円)。
  - したがって `時価総額(円) = MktCap × 1_000_000`。PER はこれを利益の合計(円)で割る。
- 対象銘柄について、週・区分(`all` と3つの区分)ごとに、`mktcap_sum`・`np_sum`・`n_target`・`n_excluded_loss` を出す。
- `per = mktcap_sum ÷ np_sum`。`eps = TOPIX の週の終値 ÷ per`(`all` だけ)。
- 集計の対象から外す銘柄は、§6.4 と同じにする。

**確かめ方**
- 実装したら、JPX の「規模別・業種別 PER・PBR」(月次)と、月末の週の値を突き合わせる(要件 F1-8 の要確認)。差が大きいときは、単位と対象銘柄を見直す。

### 6.7 主体別売買動向(`investors.csv`)
- 取り方: `/equities/investor-types` を、前回のキャッシュの最後の週の翌週から今日まで取る。初回(`--rebuild`)は、取れるいちばん古い週から取る(履歴の長さは**要確認**。要件 F1-9)。
  - 流量: 100回/分に抑え、429 のときは60秒以上待つ(要件 §7)。
- 17:00ルール: 公表日 `PubDate` の 17:00 より後にしか使えない。集計は、実行した時刻にすでに使える週だけを出す。
- 主体の対応(**要確認**。API の項目名を実物で確かめてから決める。下は V1 の項目名からの見込み):

| `subject` | 画面の名前 | 項目(差引) |
|---|---|---|
| `foreigners` | 海外投資家 | 海外投資家の差引 |
| `individuals` | 個人 | 個人の差引 |
| `investment_trusts` | 投資信託 | 投資信託の差引 |
| `business_cos` | 事業法人 | 事業法人の差引 |
| `trust_banks` | 信託銀行 | 信託銀行の差引 |
| `proprietary` | 証券会社の自己売買 | 自己計の差引 |
| `other` | その他(画面では出さない) | 生保・損保、都銀・地銀等、その他金融機関、その他法人の合計 |

- 区分の対応(`Section`): 東証全体 → `all`、プライム → `prime`、スタンダード → `standard`、グロース → `growth`。どの `Section` の値を「東証全体」とするかは**要確認**(再編の前後でつながる値を選ぶ。要件 F1-9)。
- 項目名・区分の値の対応表は、コードに直接書かず、`aggregate/investor.py` の先頭の表にまとめる(API の形が変わったとき、そこだけ直す)。
- 出力: 週(`week_start`・`week_end`)・`section`・`subject` ごとに `balance_yen` と `pub_date`。

### 6.8 日本をとりまく指標(`indicators.csv`)

| `indicator` | 取り方 | 週の値 |
|---|---|---|
| `jgb10y` | 財務省の CSV(Shift_JIS。日付は和暦 `R8.9.25` の形)。`jgbcm_all.csv` は初回だけ、以後は `jgbcm.csv`(当月)を取る。「10年」の列 | その週の最終営業日の値。なければ、その週の中でいちばん新しい日の値(2026-09-26 確定) |
| `usdjpy` | 日本銀行 時系列統計データ検索サイトの API。東京市場ドル・円スポット 17時時点(中値)の系列(系列コードは**要確認**) | 同上 |
| `wti` | EIA API v2 `petroleum/pri/spt`、系列 `RWTC`(日次) | 同上 |

- 出力: 週・指標ごとに `value` と `obs_date`(実際に使った日)。
- その週の値がまだ公表されていないときは、行を出さない。次の週の集計で埋まる(要件 §6.1)。
- 画面の「◯月◯日の週までの値」は、`obs_date` がある最後の週から作る(基本設計書 §4.10。2026-09-26 確定)。実際の公表の遅れの幅は、指標をまだ取得していないため測れていない(§12.4 の要確認)。
- 取れなかったとき(接続できない・形が違う)は、前回のキャッシュで続け、`manifest.json` の `sources` にエラーを書く。集計全体は失敗にしない。
- 利用条件(財務省の CSV)・更新の時刻は**要確認**(要件 F1-7)。

### 6.9 出力のファイル(`/Users/yone/StockPortal/data/market/`)

どれも UTF-8(BOM なし)の CSV。1行目は列名。日付は `YYYY-MM-DD`。金額は円(整数)。

| ファイル | 列 | 行の数の目安 |
|---|---|---|
| `weeks.csv` | `week_start, week_end, days, short` | 約520 |
| `turnover.csv` | `week_end, scope, s33, turnover_yen, n_codes` | 約520 × (4 + 4×33) ≒ 7万 |
| `topix.csv` | `week_end, close, ma13, ma26, ma52` | 約520 |
| `valuation.csv` | `week_end, scope, mktcap_sum, np_sum, n_target, n_excluded_loss, per, eps` | 約520 × 4 |
| `investors.csv` | `week_start, week_end, section, subject, balance_yen, pub_date` | 約260 × 4 × 7 |
| `indicators.csv` | `week_end, indicator, value, obs_date` | 約520 × 3 |
| `manifest.json` | 下の例 | — |

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-26T04:52:10+09:00",
  "as_of": "2026-09-25",
  "latest_week_end": "2026-09-25",
  "datasets": {
    "turnover":   {"latest_week_end": "2026-09-25"},
    "valuation":  {"latest_week_end": "2026-09-25"},
    "investors":  {"latest_week_end": "2026-09-18", "latest_pub_date": "2026-09-25"},
    "indicators": {"jgb10y": "2026-09-25", "usdjpy": "2026-09-24", "wti": "2026-09-22"}
  },
  "sources": {"boj": {"ok": false, "error": "timeout", "used_cache_until": "2026-09-24"}},
  "warnings": ["2026-09-24: 株価のキャッシュがない"]
}
```

- `schema_version` は、列を変えたら上げる。サーバーは知らない版を読んだら 503(`not_built`)にする。

### 6.10 書き込みの手順(画面に途中の状態を見せない)
1. `data/market.tmp/` に全ファイルを書く。
2. 行数と `manifest.json` を確かめる(前回より週が減っていないか、など)。
3. `data/market/` を `data/market.prev/` に名前を変え、`data/market.tmp/` を `data/market/` に名前を変える。
4. `data/market.prev/` を消す。
- 途中で失敗したら `data/market/` はそのまま残る。サーバーは前の週までの値を出し続ける。

---

## 7. 既存の出力の読み方(`readers/`)

### 7.1 一括分析(`readers/screen.py`)

**基準日の一覧**
- `screen_dir` の下で、名前が `YYYYMMDD`(8桁の数字だけ)のフォルダを探す。`20260911_trial` などは読まない。
- `verdicts.csv` と `report.md` の両方があるフォルダだけを、基準日とする。
- `GET /api/weekly/dates` では、基準日ごとに、`picks_<日付>.md` と `candidates/<日付>/candidates.csv` があるかも返す(タブの件数と「この週のデータはありません」に使う)。

**`verdicts.csv` の読み方**
- 文字コードは BOM 付き UTF-8。
- 先頭の5列は `コード, 銘柄名, 市場, 業種コード, 時価総額(億円)`。
- 残りの列は、手法ごとに「`手法名(時間軸)`」と「`手法名_局面`」の2列。**列の順番は画面の順と違う**(実物はボリンジャーバンドが先)ので、列名で探す。
  - 列名を `^(.+)\((日足|週足)\)$` で分け、手法名と時間軸を取る。時間軸はそのまま見出しに出す(要件 §5.3「データの時期の注意」)。
- 手法名の対応と、画面の順

| 順 | `key` | `verdicts.csv` の手法名 | `results.jsonl` のキー | 画面の名前 |
|---|---|---|---|---|
| 1 | `granville` | グランビルの法則 | `granville` | グランビル |
| 2 | `earnings-breakout` | 決算ブレイクアウト | `earnings-breakout` | 決算ブレイクアウト |
| 3 | `flag-pennant` | フラッグ/ペナント | `flag-pattern` と `pennant` | フラッグ/ペナント |
| 4 | `bollinger-bands` | ボリンジャーバンド | `bollinger-bands` | ボリンジャーバンド |
| 5 | `macd` | MACD | `macd` | MACD |

- 判定の値の対応: `買い` → `buy`、`中立` → `neutral`、`売り` → `sell`、`判定不能` → `unknown`、`食い違い` → `conflict`、`失敗` → `unknown`。これ以外の値が来たら `unknown` にし、ログに警告を書く。
- **判定のラベルは `verdicts.csv` を正とする(2026-09-26 決定)。** `results.jsonl` の `verdict` は使わない。`results.jsonl` は根拠(シグナル・典拠・値)の表示にだけ使う。ラベルの決め方は一括分析の側にあるので、ポータルは CSV のとおりに出す(D2)。
  - 2026-09-25 の実物 977 銘柄を全件突き合わせて、2種類の食い違いを確認した。
  - **①「判定不能」が `results.jsonl` では `neutral` になる(14 か所)。** MACD 4・決算ブレイクアウト 4・フラッグ/ペナント 4(2手法で各2)・グランビル 2。いずれも上場して間もなく週足の本数が足りない銘柄(543A・581A・547A ほか)で、`phase_label` だけが `判定不能` になっている。`verdict` を使うと「データが足りない」が「判断した結果の中立」に見え、R5 に反する。
  - **②「食い違い」は `verdicts.csv` にしかない。** `verdicts.csv` の「フラッグ/ペナント(週足)」1列は、`results.jsonl` の `flag-pattern` と `pennant` の2手法を合成した値である(977 銘柄中 180 か所で、列の値と2手法の組み合わせが1対1に対応しない)。2手法が逆を向いた4件(8591 オリックス・9708 帝国ホテル・3038 神戸物産・186A アストロスケールHD)に `食い違い` が入る。この値は `results.jsonl` 側に存在しないので、合成をポータルで再現しない。
- 局面の列は、そのまま文字列で持つ。
- 知らない手法の列が増えたときは、読み飛ばしてログに書く(表の列は増やさない。2026-09-26 確定)。

**`results.jsonl` の読み方**
- 1行1銘柄の JSON。同じ銘柄が複数行あるので、**最後の行**を採る(要件 §5.3)。
- `status` が `ok` でない銘柄は、判定表から外し、「失敗した銘柄」に入れる(基本設計書 §5.4 (5))。理由は、その行にある失敗の説明(項目名は実物で**要確認**)。
- 根拠の API では、`results` の中の `MethodResult` を、手法ごとに次の形で返す。
  - `verdict`・`phase_label`・`timeframe`・`signals`(日付の新しい順に並べ替える)・`notes`。
  - 各シグナルの `basis` に「仮置き」の文字があれば `provisional: true` を付ける。画面はそれを見て、典拠の後ろに「(仮置き)」を出す(R4)。
  - 「判定と局面」の前提の文(例: 「週足・13週線・判定に使う範囲は直近8本」)は、`state` の値から作らず、手法ごとに決まった文を画面に持つ(2026-09-26 確定)。`state` から作れるかは**要確認**(§12.4)。作れると分かれば、次のスプリントで差し替える。
  - フラッグ/ペナントは、`flag-pattern` と `pennant` の2つの結果を、見出しを分けてそのまま並べる。

**失敗した銘柄**
- `report.md` の「分析できた ◯ / 失敗 ◯」の行と、`results.jsonl` の `status` の両方を見る。数が合わないときは、`results.jsonl` を正とし、ログに警告を書く。

### 7.2 来週の買い注文の候補(`readers/picks.py`)

**読むファイルと、どこから何を取るか**

| 画面の欄(基本設計書 §5.5) | 取る場所 |
|---|---|
| 注文の有効期間 | 取引カレンダー(基準日の翌営業日から、同じ週の最終営業日まで)。`picks_*.md` の「注文の有効期間」の行と食い違ったら、ログに警告を書き、md の方を出す |
| 決済のルール | `picks_*.md` の「決済」の行 |
| 前提を満たした銘柄と計画の数 | `picks_*.md` の「前提(…)を満たした銘柄 ◯、計画 ◯ 件」の行(正規表現で取る) |
| 選定基準 | `picks_*.md` の「選定基準: {…}」の辞書(`ast.literal_eval` で読む)。札の文言は §7.2 の下の表で作る |
| 候補のカード | `picks_*.csv`(1行1候補。約130列のうち下の表の列) |
| 同じ銘柄の指値の段 | `picks_*.md` の各候補の節の「同じ銘柄の指値の段」の表 |
| 参考: 上位10銘柄と落ちた理由 | `picks_*.md` の「参考: …」の節の表 |
| 検証の限界 | `picks_*.md` の「この数値の読み方(検証で分かっている限界)」の節(箇条書きと表) |

- **指値の段・参考・検証の限界は、Markdown の表から読む。** どの段を選ぶか、落ちた理由は何かは J-Quants 側のロジックなので、`plans_*.csv` から作り直さない(D2)。
  - そのため、`plans_<基準日>.csv` は**読まない**(2026-09-26 決定。要件定義書・基本設計書の読み元の表からも外した)。
- Markdown の読み方: `## ` の見出しで節に分け、節の中の最初の表(`|` で始まる行のかたまり)を、1行目を列名として読む。数字の `,` と `%` は外して数にする。
- 候補が0件の週: CSV の行が0で、md に候補の節がない。このとき `picks: []` を返し、画面は「今週は見送り」を出す(R5)。

**`picks_*.csv` から使う列**

| 列 | 画面 |
|---|---|
| `code`・`name`・`sector_name` | 見出し |
| `close` | 基準日の終値 |
| `entry` | 買いの指値。終値からの% = `entry ÷ close − 1` |
| `stop` | 損切り。指値からの% = `stop ÷ entry − 1` |
| `target` | 目標。指値からの% = `target ÷ entry − 1` |
| `rr` | リワード ÷ リスク |
| `confluence` と、md の「指値の根拠(重なる支持線 ◯ 本)」の行 | 重なる支持線の本数と名前(名前は md から取る) |
| `p_fill`・`p_target`・`p_stop`・`p_time` | 確率(推定値)の4つ |
| `ev_fill`・`ev_order` | 期待リターン |

- 市場の区分は CSV にないので、最新の銘柄一覧(§5.8)から付ける。
- 値の単位は **`p_*`・`ev_*` のどれも割合(0〜1)**(2026-09-26 確定)。md の表示と突き合わせて確認した(日本郵政 2026-09-25: `p_fill` 0.4995 → md「50.0%」、`ev_fill` 0.02388 → md「2.4%」、`ev_order` 0.01193 → md「1.2%」)。画面で100倍して % にする。

**選定基準の札の文言**(`criteria` の辞書のキー → 札)

| キー | 札 |
|---|---|
| `min_reward_pct`・`max_reward_pct` | 目標 +8〜12% |
| `min_rr`・`max_rr` | R:R 1.5〜2.0 |
| `limit_only` | 指値のみ |
| `min_confluence` | 支持線の重なり5本以上 |
| `min_p_fill` | 約定確率35%以上 |
| `max_risk_pct` | 損切りまで15%以内 |
| `max_picks`・`one_per_sector` | 業種を分けて最大3銘柄 |

- 値は辞書から入れる(上の数字は 2026-09-25 の例)。`-9.0` や `1.0` のように「効いていない」値のキー(`min_ev_order` など)は札にしない。表にないキーが来たら、`キー: 値` のまま札にする。

### 7.3 買い候補(`readers/candidates.py`)
- `candidates_dir/<YYYYMMDD>/candidates.csv`。BOM 付き UTF-8。
- 列の対応

| CSV の列 | API の項目 |
|---|---|
| `コード` / `銘柄名` / `業種コード` / `時価総額(億円)` | `code` / `name` / `s33` / `market_cap_oku` |
| `手法` / `水準` / `成立した足` | `method` / `level` / `formed_on` |
| `想定の買値(基準日の終値)` | `entry` |
| `損切りの支持線` / `損切り価格` | `stop_line` / `stop` |
| `支持線の守った割合(%)` / `支持線に触れた回数` | `hold_pct` / `touches` |
| `リスク(%)` / `リワード(%)` / `リスクリワード` | `risk_pct` / `reward_pct` / `rr` |
| `詳細` | `detail`(空が多い。画面では出さない。2026-09-26 確定) |

- 手法の絞り込みの対応(`手法` の値 → ボタン): `グランビルの法則` → グランビル、`決算ブレイクアウト` → 決算ブレイクアウト後の押し目、`フラッグ`・`ペナント` → フラッグ・ペナントの上抜け、`ボリンジャーバンド` → ボリンジャーバンド。知らない値は「すべて」のときだけ出す。
- 並び順はリスクリワードの大きい順(基本設計書 §5.6)。順位はこの並びで1から振る。
- 同じ銘柄が複数の手法で出たときも、行をまとめない。

### 7.4 取引カレンダー(`readers/calendar.py`)
- 集計と同じく `jquants_raw/markets__calendar/` の、`to=` がいちばん新しいファイルを読む。
- 使うところ: 基準日の曜日、注文の有効期間(F1-5)、`expected_week_end`(§5.7)。
- カレンダーの `to=` が今日より前で、翌週の営業日が分からないときは、注文の有効期間を md の行から出す。

---

## 8. 画面(`web/`)

### 8.1 URL と画面の対応(SvelteKit のルート)

| URL | ファイル | 画面 |
|---|---|---|
| `/` | `routes/+page.ts` | `/market` へ移す |
| `/market` | `routes/market/+page.svelte` | G-11 |
| `/market/segments` | `routes/market/segments/+page.svelte` | G-12 |
| `/market/sectors` | `routes/market/sectors/+page.svelte` | G-13 |
| `/weekly/verdicts` | `routes/weekly/verdicts/+page.svelte` | G-21 |
| `/weekly/picks` | `routes/weekly/picks/+page.svelte` | G-22 |
| `/weekly/candidates` | `routes/weekly/candidates/+page.svelte` | G-23 |
| `/settings` | `routes/settings/+page.svelte` | G-30(2026-09-26 追加) |
| 上にない URL | `routes/+error.svelte` | G-90 |

- `adapter-static` の SPA の書き出し(`fallback: 'index.html'`)。サーバーは、ファイルに当たらない URL に `index.html` を返す(§5.1)。
- **URL のパラメータが画面の状態の元**(`period`・`scope`・`date`)。ボタンを押したら URL を書き換え(`goto(..., {replaceState: false, keepFocus: true, noScroll: true})`)、URL が変わったらデータを読み直す。これで、戻るボタンと画面の引き継ぎ(基本設計書 §3.1)が同じ仕組みで動く。
- URL に載せないもの(画面の中だけで持つ): 主体別の選んだ主体、判定表の絞り込み・ページ、根拠を開いた行。どれも画面を離れたら消える(基本設計書 §3.1)。
  - 株数の目安の資金も URL には載せないが、`localStorage` に保存して次に開いたときの初期値にする(2026-09-26 決定。§8.8)。
  - 選んだ主体は、G-12 の中で区分を切り替えても残す(同じ画面の中の状態なので残る)。

### 8.2 部品の一覧(`lib/components/`)

| 部品 | 使う画面 | 役目 |
|---|---|---|
| `AppHeader` | 全画面 | サイト名、上部メニュー、銘柄検索、データの時点(`/api/status`) |
| `DataStamp` | `AppHeader` の中 | 2行の時点表示と「更新が遅れています」 |
| `SymbolSearch` | `AppHeader` の中 | 入力 → 250ms 待って `/api/search` → 候補(最大10件)。↑↓と Enter で選べる |
| `MarketNav` | G-11〜G-13 | 階層ナビと期間ボタン |
| `WeeklyNav` | G-21〜G-23 | 見出し、基準日の ◀・一覧・▶、タブ(件数付き) |
| `Disclaimer` | 全画面 | 注意書き。`variant="box"`(週次)/ `"footer"`(市場概況)と、画面ごとの一言 |
| `Card` | 全画面 | 読み込み中の灰色の形、失敗の表示と「再読み込み」(基本設計書 §4.10) |
| `StatCard` | G-11・G-12 | 大きな数字と補足 |
| `TopixTurnoverChart` | G-11 | §8.4 |
| `AllocationBar` | G-11 | 区分のシェアの横帯 |
| `InvestorFlow` | G-11・G-12 | 積み上げ棒 + TOPIX、主体の一覧(凡例)、すべて選ぶ・外す |
| `ValuationPanel` | G-11 | PER・EPS のカード、値動きの分解、2つのチャート |
| `IndicatorTile` | G-11 | 指標1つ分(数値と小さな線のチャート) |
| `SegmentPanel` | G-12 | 区分1つ分のパネル |
| `SectorHeatmap` | G-13 | 業種の表とヒートマップ |
| `VerdictFilters` / `VerdictTable` / `EvidenceRow` | G-21 | 絞り込み、判定表、根拠 |
| `VerdictBadge` | G-21 | 判定のラベル(色 + 文字) |
| `PickCard` / `RungTable` / `PositionSizer` / `Collapsible` | G-22 | 候補のカード、指値の段、株数の目安、開閉できる欄 |
| `CandidateTable` | G-23 | 買い候補の表 |
| `TradingViewLink` | 全画面 | §8.7 |

- 1つのカードのデータの読み込みに失敗しても、ほかのカードは出す。そのため、画面の API は1本でも、画面の側ではカードごとに `null` を見て、欠けたカードだけ失敗の表示にする(2026-09-26 確定)。G-11 の読み元は既存の出力・ポータルの集計・外部の指標に分かれているため、1つ欠けても他を出せる形にする(R5)。

### 8.3 画面ごとの API とカード

| 画面 | 呼ぶ API | 呼び直すとき |
|---|---|---|
| G-11 | `/api/market/japan?period` | 期間を変えたとき |
| G-12 | `/api/market/segments?period` | 期間を変えたとき。区分・主体の切り替えでは呼ばない(3区分分を最初に受け取る) |
| G-13 | `/api/market/sectors?period&scope` | 期間か対象を変えたとき |
| G-21 | `/api/weekly/dates`、`/api/weekly/{date}/verdicts`、根拠を開いたとき `/api/weekly/{date}/verdicts/{code}` | 基準日を変えたとき。絞り込みでは呼ばない |
| G-22 | `/api/weekly/dates`、`/api/weekly/{date}/picks` | 基準日を変えたとき |
| G-23 | `/api/weekly/dates`、`/api/weekly/{date}/candidates` | 基準日を変えたとき |

- 取った応答は、画面の中で URL ごとに持っておく(同じ期間に戻ったときに呼び直さない)。ページを再読み込みしたら捨てる。

### 8.4 チャート(ECharts)

| チャート | 形 | 設定の要点 |
|---|---|---|
| TOPIX と売買代金(G-11 (3)) | 上下2つの `grid`、横軸を共有 | 上: 線 4本(終値・13・26・52週線)、凡例で線の表示を切り替え。下: 棒(週合計)+ 線(13週平均)。`tooltip.trigger='axis'` で基本設計書のとおりの項目を出す。営業日5日未満の週は、下の横軸の目盛りの下に ▲ を `markPoint` で描く |
| 主体別売買動向(G-11 (5)・G-12 (3)) | 積み上げ棒 + 線 | 棒は主体ごとの `series`、`stack` を正と負で分ける(`stack: 'pos'` / `'neg'`。値を正と負の2系列に分けて渡す)。TOPIX は左の軸、棒は右の軸。未公表の週は `markArea` で網かけし「未公表」。選んだ主体だけを `series` に入れ、右の軸の最小・最大は、選んだ主体の正の合計の最大と負の合計の最小から計算する |
| EPS・PER(G-11 (6)) | 線 2つを横に並べる | — |
| 指標(G-11 (7)) | 小さな線 | 軸の数字は最小限 |
| シェアの推移(G-12 (2)) | 線 + 点線 + 網かけ + 薄い棒 | 期間平均は `markLine`、直近の範囲は `markArea`、売買代金は第2の縦軸の薄い棒。縦軸は区分ごとに自動 |
| 業種のヒートマップ(G-13) | `heatmap` | 値を −30〜+30 に丸めて、`visualMap` の連続の色(青 `#2F6690` 〜 白 〜 赤 `#B5452B`)。行は業種(並べ替え済み)、列は週 |

- 色は `lib/theme.ts` に1か所でまとめる(基本設計書 §4.8)。値は**ハードコードしない**。
  - サーバーは `GET /api/theme` で `config.toml` の `[theme]` を返す。画面は起動時にそれを読み、CSS 変数(`--bg`・`--buy-fg` など)として `:root` に流し込む。
  - `localStorage` のキー `stockportal.theme` に端末の上書きがあれば、そちらを後から重ねる(設定画面 G-30)。
  - ECharts の色も、同じ CSS 変数から `getComputedStyle` で読む。チャートの中で16進数を直接書かない。
- スマホ(768px 未満)では、凡例を下に移し、横軸の目盛りを間引く。チャートの幅は親の幅に合わせ、`ResizeObserver` で描き直す。
- ヒートマップと判定表は、表の中だけ横に動かせるようにする(`overflow-x: auto` の枠で囲む)。

### 8.5 書式(`lib/format.ts`)
基本設計書 §4.9 を関数にする。どの画面も、数値はこの関数を通して出す。

| 関数 | 入力 | 出力の例 |
|---|---|---|
| `cho(yen, digits=1)` | 円 | `33.7兆円` |
| `choSigned(yen)` | 円 | `+1.52兆円`(小数2桁) |
| `oku(value)` | 億円 | `250,544` |
| `price(v, digits=0)` | 円・ポイント | `2,498`、`2,581.0` |
| `pct(v, {signed})` | % | `7.2%`、`+18%` |
| `pt(v)` | pt | `▲ +1.2pt` / `▼ −0.8pt` |
| `times(v, digits=2)` | 倍 | `1.11倍`、PER は `15.3倍` |
| `bp(v)` | bp | `+17bp` |
| `date(d, {weekday})` | `YYYY-MM-DD` | `2026-09-18(金)` |
| `weekRange(start, end)` | 2つの日付 | `09/14〜09/18` |

- 値が `null` のときは、どの関数も `—` を返す(0 と区別する)。
- 負の符号は `−`(U+2212)を使う(基本設計書の例に合わせる)。
- 丸めは四捨五入(`Math.round` を桁に合わせて使う。0.5 の扱いの違いは気にしない)。

### 8.6 判定表の絞り込みと並べ替え(画面の中で行う)

全行(約1,000行)を受け取り、条件が変わるたびに次を計算する。1秒以内(基本設計書 §9)は、この件数なら十分に間に合う。

1. **絞り込み**(すべて AND)
   - 買い判定の数: 行ごとに、5つの手法の判定が `buy` **または `conflict`** の数を数える(2026-09-26 決定。`conflict` はフラッグとペナントが逆を向いた状態で、片方は `buy` のため)。選んだ数以上の行を残す。**この数は表に出さない**(R1・R2)。この数での並べ替えも置かない(2026-09-26 決定)。
   - 手法 + 判定 + 局面: 選んだ手法の判定と局面が、選んだものに一致する行を残す。局面の選択肢は、その基準日の全行から、選んだ手法の局面を集めて作る。
   - 市場・業種: 一致。
   - 時価総額: 下限以上・上限以下。
2. **並べ替え**(固定。基本設計書 §5.4 (3))
   - 並べ替えのキー = `[rank(granville), rank(earnings-breakout), rank(flag-pennant), rank(bollinger-bands), rank(macd), −market_cap_oku]`。
   - `rank`: `buy`=0、`neutral`=1、`unknown`=2、`conflict`=2、`sell`=3(2026-09-26 確定)。
   - `conflict` は絞り込みでは `buy` として数えるが(上の 1)、並べ替えでは `unknown` と同じ位置に置く。絞り込みは「買いの証拠がいくつあるか」で行を拾う条件、並べ替えは「確かな買い」を上に並べるためのもので、役割が違う(基本設計書 §5.4 (3))。
   - キーは、基準日のデータを受け取ったときに1回だけ作っておき、絞り込みのたびには作らない。
3. **ページ送り**: 1ページ50行。条件が変わったら1ページ目に戻す。
4. **銘柄の検索から来たとき**(`/weekly/verdicts?code=8306`): 絞り込みを既定にし、その行があるページを開き、その行の根拠を開いて、その行までスクロールする。対象外の銘柄なら、表の上に「この銘柄は一括分析の対象外です…」と「TradingView で開く」を出す(基本設計書 §4.5)。
   - `code` のパラメータは、この用途のためにこの文書で足す(2026-09-26 確定)。

- 根拠を開いた行は同時に1行だけ。別の行を開いたら、前の行を閉じる。

### 8.7 TradingView へのリンク
- `https://jp.tradingview.com/chart/?symbol=TSE%3A<コード>`(2026-09-26 確定。実機で `TSE:8306`・`TSE:285A` を確認。基本設計書 §4.7)。
- コードは、5文字で末尾が `0` のとき、末尾を落とす(`287A0` → `287A`、`83060` → `8306`)。4文字のときはそのまま。
- `<a target="_blank" rel="noopener noreferrer">`。

### 8.8 株数の目安(G-22 (5))
- 入力は `inputmode="numeric"`。数字以外を消し、表示は3桁区切りにする。
- 計算は基本設計書 §6.10 のとおり。候補ごとに、その候補の指値と損切りで計算する。
- 資金は `localStorage` のキー `stockportal.capital` に保存する(2026-09-26 確定。基本設計書 §5.5 (5))。次に開いたときの初期値にする。URL には載せない。

### 8.9 スマホの表示
- 切り替えの横幅は 768px(CSS の `@media (max-width: 767px)`。2026-09-26 確定)。
- 押せるものは高さ 44px 以上。
- G-21 の判定表は、スマホでは局面の行を出さず、判定のラベルだけにする(基本設計書 §4.2)。

---

## 9. 非機能の作り方

### 9.1 開ける範囲(家の外からは開けない)
3段で守る。

| 段 | やること |
|---|---|
| 1. 家のルーター | ポートの転送(ポートフォワード)をしない。家の外から Mac に届かない(前提。設定は変えない) |
| 2. 接続元の IP | ミドルウェアで、接続元が次のどれかでなければ 403 を返し、本文を返さない: `127.0.0.1`・`::1`・`10.0.0.0/8`・`172.16.0.0/12`・`192.168.0.0/16`・`fe80::/10`・`fd00::/8` |
| 3. `Host` ヘッダー | `allowed_hosts`(設定)と、Mac の今の LAN の IP アドレスのどれでもなければ 403。悪意のあるウェブサイトから、DNS リバインディングでこのポータルを読まれるのを防ぐ |

- ほかにも次を守る。
  - API は `GET` だけ。書き込む API は作らない。
  - CORS のヘッダーは付けない(ほかのサイトの画面から API を読めないようにする)。
  - macOS のファイアウォールで、Python の受信を許可する(初回に確認が出る)。

### 9.2 秘密情報
- API キーは、集計のバッチだけが読む。サーバーの API は、キーも、キーのファイルのパスも返さない(要件 §7)。
- キーのファイルはリポジトリの外(`/Users/yone/J-Quants/.env`、`/Users/yone/StockPortal/.env`)。`.gitignore` に `.env` を入れておく。

### 9.3 表示の速さ(3秒以内。2026-09-26 確定)
- 市場概況: 集計の結果をメモリに持ち、期間の計算は数十ミリ秒で済む見込み。
- 判定表: 約1,000行の JSON を gzip で返す(約60KB)。
- `results.jsonl` は索引を作るまでに数秒かかるので、サーバーの起動時と、新しい基準日を見つけたときに、裏で作っておく。

### 9.4 可用性
- サーバーは launchd の `KeepAlive` で、落ちたら起動し直す。
- データの更新の失敗は、実行状況の記録(§4.6)と「更新が遅れています」(§5.7)で分かる。

---

## 10. 動かし方

### 10.1 launchd(`deploy/launchd/`)

| ラベル | 起動 | 動かすもの | ログ |
|---|---|---|---|
| `com.yone.stockportal.server` | ログイン時(`RunAtLoad`)、落ちたら再起動(`KeepAlive`) | `uvicorn stockportal.app:app --host 0.0.0.0 --port 8765` | `logs/server.log` |
| `com.yone.stockportal.weekly` | 土曜 3:00(`StartCalendarInterval`) | `caffeinate -i -m -s python -m stockportal.batch.weekly` | `logs/weekly/<基準日>_<手順>.log` |

- どちらも `WorkingDirectory` は `/Users/yone/StockPortal/app/server`、環境変数 `STOCKPORTAL_CONFIG=/Users/yone/StockPortal/config.toml`。
- 既存の `com.yone.technicalanalysis.screen` には触れない。

#### 土曜の処理中にスリープさせない(2026-09-26 決定)

実測で、土曜の一括分析が Mac のスリープで大きく遅れる回があった。

| 実行日(土曜) | 開始 | 終了 | 壁時計 | 処理の内部経過 |
|---|---|---|---|---|
| 2026-09-19 | 03:13:04 | 12:16:07 | **9時間03分** | 37.8分 |
| 2026-09-26 | 03:00:05 | 03:38:02 | 38分 | 37.9分 |

処理そのものは約38分で、9時間かかった回は実行中に繰り返しスリープしていた(`pmset -g log` に `Entering Sleep state due to 'Clamshell Sleep' ... Using Batt` が記録されている)。省電力設定はバッテリーが `sleep 1`(1分でスリープ)、AC が `sleep 0`。既存の plist にスリープ対策はない。

対策は3つを重ねる。

| # | 対策 | 効く条件 |
|---|---|---|
| 1 | 週次の後続の処理を **`caffeinate -i -m -s`** で包んで起動する | `-i`(アイドルスリープ)と `-m`(ディスク)はバッテリーでも有効。`-s` は AC 電源のときだけ有効(`man caffeinate`) |
| 2 | **`sudo pmset repeat wakeorpoweron SAT 02:55`** を設定する(§10.3 の手順0) | 常に有効。土曜 3:00 に起きている状態を作る |
| 3 | **土曜の夜は AC 電源につないでおく**(運用の前提) | AC は `sleep 0` なので、蓋を閉じてもスリープしない |

- 1 の `caffeinate` は**既存の一括分析も守る**。後続の処理は 3:00 に起動して一括分析の完了を待つので、待っている間もアサーションを保持し続け、同時に動いている一括分析もスリープに巻き込まれない。既存のコードには手を入れずに済む(D1)。
- **蓋を閉じてバッテリーで放置した週は、コードでは防げない**(Clamshell Sleep は `caffeinate` では止まらない)。そのため 3 を運用の前提として置く。つないでいなかった週は、画面の「更新が遅れています」(§5.7)で気づける。
- 普段の使い方に影響する設定(`pmset -b disablesleep 1` など)は入れない。

### 10.2 ログ
- 置き場所: `/Users/yone/StockPortal/logs/`。
- サーバー: 1行1件、`時刻 レベル 内容`。アクセスは、パス・状態コード・時間だけを書く。
- バッチ: 手順ごとのファイル。先頭に開始の時刻と、呼んだコマンド、最後に終了コードを書く。
- 古いログは、26週より前のものを週次の後続の処理の最後に消す(2026-09-26 確定)。既存のログの量は TechnicalAnalysis 24KB・J-Quants 100KB(2026-09-26 実測)で、26週分でも数MBに収まる。

### 10.3 入れ方(`deploy/install.sh`)
0. **初回だけ**、次の2つを先に済ませる。
   - `brew install uv` と `uv python install 3.12`(§2.1)。
   - `sudo pmset repeat wakeorpoweron SAT 02:55`(2026-09-26 決定)。土曜 3:00 に Mac が起きている状態を作る。`pmset -g sched` で予約を確かめる。
   - `sudo scutil --set LocalHostName stockportal`(2026-09-26 決定)。スマホから `http://stockportal.local:8765` で開けるようにする。既定の `LocalHostName` は macOS が自動で採番するため(2026-09-26 時点は `yone-3`)、ネットワーク環境によって変わる。明示的に設定して固定する。設定後、`scutil --get LocalHostName` が `stockportal` を返すことと、`ping stockportal.local` が通ることを確かめる。
1. リポジトリの `main` を `/Users/yone/StockPortal/app/` に書き出す(`git worktree` か `git archive`)。作業中のブランチの変更が、動いているポータルに混ざらないようにするため。
2. `server/` で `uv sync`(ポータルの仮想環境を作る)。
3. `web/` で `npm ci && npm run build`(`web/build/` に書き出す)。
4. `config.toml` がなければ、見本をコピーする。
5. plist を `~/Library/LaunchAgents/` に置き、`launchctl bootstrap` で読み込む。すでにあれば入れ替える。
6. 初回だけ、`python -m stockportal.batch.aggregate --rebuild` を動かす。

---

## 11. テスト

| 種類 | 対象 | やり方 |
|---|---|---|
| 読み込み | `readers/` | 2026-09-25 の実物から、10銘柄分を切り出した小さなファイルを `tests/fixtures/` に置く。列の順番が違うもの、同じ銘柄が複数行ある `results.jsonl`、`_trial` のフォルダ、0件の `picks_*.md` も用意する |
| 集計 | `batch/aggregate/` | 3週・5銘柄ほどの作ったデータで、週の区切り(祝日・半日立会)、区分・業種の振り分け、17:00ルール(17:00ちょうど・17:01の開示)、赤字予想の除外、本決算での予想の切り替えを確かめる |
| 計算 | `calc/` | 基本設計書 §6 の式ごとに、手で計算した値と比べる。`null` を含む期間も確かめる |
| API | `api/` | FastAPI の `TestClient` で、正しいパラメータ、不正なパラメータ(既定値になる)、ないデータ(404)、家の外の IP(403)、知らない `Host`(403) |
| 表示の約束 | API の応答 | 判定表の応答に、合計点・総合判定・買い判定の数の項目がないこと(R1・R2) |
| 画面の計算 | `lib/format.ts`、判定表の絞り込み・並べ替え | Vitest |
| 通しの確認 | 全体 | 実物の 2026-09-25 のデータで動かし、G-11〜G-23 を Mac とスマホ(375px)で開く。数値は、既存の md(`report.md`、`picks_*.md`)と突き合わせる |
| 集計の水準 | EPS・PER | JPX の規模別・業種別 PER と突き合わせる(§6.6) |

---

## 12. 基本設計書との対応と、この文書で決めたこと

### 12.1 基本設計書の反映先

| 基本設計書 | この文書 |
|---|---|
| §2 画面一覧、§3 画面の移り方 | §8.1 |
| §3.1 画面をまたいで引き継ぐもの | §8.1 |
| §4.3 データの時点の表示 | §5.7 |
| §4.4 期間 | §5.6 |
| §4.5 銘柄の検索 | §5.8、§8.6 の 4 |
| §4.7 TradingView へのリンク | §8.7 |
| §4.8 色、§4.9 書式 | §8.4、§8.5 |
| §4.10 データが足りないとき | §5.6、§5.9、§8.2 |
| §5.1〜§5.3 市場概況の画面 | §5.3、§6、§8.3、§8.4 |
| §5.4 判定表 | §5.4、§7.1、§8.6 |
| §5.5 来週の買い注文の候補 | §7.2、§8.8 |
| §5.6 買い候補 | §7.3 |
| §6 計算方法 | §5.6(期間に依存するもの)、§6(週ごとの値) |
| §7 更新のタイミングと読み元 | §4、§6.1、§7 |
| §8 エラーと例外 | §5.9、§9.1 |
| §9 非機能 | §9 |

### 12.2 この文書で新しく決めた値(2026-09-26 にすべて確定。下の一覧の番号は §12.4 の解消状況と対応する)
1. 技術スタック(§2): FastAPI・SvelteKit・ECharts・ファイル保存・ポータル専用の Python 環境。
2. ポート 8765、設定ファイルの置き場所と項目(§3.3)。
3. 動かす版をリポジトリの `main` から `/Users/yone/StockPortal/app/` に書き出す(§10.3)。
4. 週次の後続の処理: 基準日を `--as-of` で渡す、二重起動を防ぐ、手順ごとの時間の上限、実行状況の記録の形(§4)。
5. 一括分析が3時間でそろわないときは、手順1・2を飛ばし、手順3だけ動かす(§4.1)。
6. 市場概況の集計: 出力のファイルの形(§6.9)、差分の計算で最後の4週を作り直す(§6.2)、旧区分を新区分に読み替えずに別に保存する(§6.4)。
7. 指標の週の値が最終営業日にないときは、その週の中でいちばん新しい日の値を使う(§6.8)。
8. API の一覧と応答の形(§5)。数値は丸めずに返し、書式は画面で行う。
9. ~~主体別の要約は、主体を外しても変えない(§5.3)~~ → **2026-09-26 確定**。
10. 判定表: 全行を1回で返し、画面の中で絞り込む。`失敗` は判定不能と同じ扱い。`status` が `ok` でない銘柄は表から外す(§7.1、§8.6)。
11. 検索から判定表を開くときの URL `?code=`(§8.6)。
12. 根拠の「前提」の文は、手法ごとに決まった文を画面に持つ(§7.1)。
13. ログを26週で消す(§10.2)。

### 12.3 実物を見て上流の文書を直したところ(2026-09-26 決定・反映済み)
実物のファイルを確認して、要件定義書・基本設計書の記述と食い違っていた3点を、次のように決めて上流にも反映した。

| # | 内容 | 決定 | 反映先 |
|---|---|---|---|
| 1 | `plans_<基準日>.csv`(全計画。8.8MB・7,736行)を読むか | **読まない。** 指値の段・参考の上位10銘柄・検証の限界は `picks_<基準日>.md` の表から読む。全計画から段を選び直すと J-Quants 側の選定ロジックの複製になる(D2)し、結果は `.md` の表と同じになる | 要件定義書 F2-2・§5.2 の読み元の表、基本設計書 §7.2、本書 §7.2 |
| 2 | 決算短信の翌期の予想の項目名 | **`NxFNp`**(小文字の p)。キャッシュの実物で確認済み(`fins__summary` の項目に `NxFNp`・`NxFNp2Q` があり、`NxFNP` は存在しない) | 要件定義書 F1-8、本書 §6.6 |
| 3 | 判定のラベルの正本 | **`verdicts.csv` を正とする。** `results.jsonl` の `verdict` は使わず、根拠の表示にだけ使う。977銘柄の全件突き合わせで、`判定不能` が `neutral` になる 14 か所と、`verdicts.csv` にしかない `食い違い`(フラッグ/ペナントの2手法の合成)を確認した | 本書 §7.1 |

### 12.4 未決・要確認(実装の前か、実装の最初に確かめる)

**未決(基本設計書 §10.4 から、作り方に関わるもの)**
1. ~~技術スタック(要件 §9-1)~~ → **2026-09-26 確定**(§2)。
2. ~~売買代金の集計範囲(ETF・REIT などを含めるか)~~ → **2026-09-26 確定**。ETF・REIT(`0109`)と TOKYO PRO MARKET(`0105`)は外す。東証公表値には一致させない(§6.4)。設定で切り替えられるようにはしておく。
3. 2022年4月より前の区分の並べ方。旧区分は別に保存しておく(§6.4)。

**要確認(実物を見て決める)**
1. 投資部門別情報の API の項目名、`Section` の値、履歴の長さ、`PubDate` の曜日と時刻(§6.7)。
2. ~~決算短信の `DocType` の値ごとの `FNP`・`NxFNp` の入り方~~ → **2026-09-26 確認済み**(§6.6。`FYFinancialStatements_*` は `NxFNp`、四半期と予想の修正は `FNP`、配当だけの修正はどちらも空)。
3. ~~`MktCap` の単位~~ → **2026-09-26 確定: 百万円**(§6.6)。
4. 日本銀行の API で、ドル円 17時・中値の系列コード(§6.8)。
5. 財務省 CSV の利用条件と更新の時刻、EIA の公表の遅れ(§6.8)。
6. ~~`picks_*.csv` の `p_*`・`ev_*` の単位~~ → **2026-09-26 確定: どれも割合(0〜1)**(§7.2)。画面で100倍して % にする。
7. `results.jsonl` で `status` が `ok` でないときの、失敗の理由の項目名(§7.1)。
8. 旧区分(東証1部・2部・マザーズ・JASDAQ)の `Mkt` のコードの一覧(§6.4)。
