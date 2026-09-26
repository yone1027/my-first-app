# server(サーバーとバッチ)

詳細設計書 [docs/detailed-design.md](../docs/detailed-design.md) の §3〜§7・§9〜§11 の実装。

## 開発環境

本番は `uv` が管理する Python 3.12(詳細設計書 §2.1)。`uv` は公式の配布バイナリで
入れる(`brew install uv` は bottle が無くソースからビルドになるので使わない)。

```
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
```

手元で動かすだけなら任意の 3.12 以降で足りる。

```
python3 -m venv .venv                     # リポジトリの直上で
.venv/bin/pip install -e 'server[dev]'
```

## 設定

`STOCKPORTAL_CONFIG` に設定ファイルのパスを渡す。渡さなければ
`config/config.example.toml` を使う(パスは実機に合わせてある)。

集計の出力先だけをリポジトリの中に向けた開発用の設定を作る場合:

```
mkdir -p .dev/StockPortal/{data,logs}
sed -e 's#^portal_data.*#portal_data    = "'"$PWD"'/.dev/StockPortal/data"#' \
    -e 's#^logs.*#logs           = "'"$PWD"'/.dev/StockPortal/logs"#' \
    config/config.example.toml > .dev/config.toml
```

## 動かす

```
# 市場概況の集計(初回は --rebuild。521週で約2分)
cd server && STOCKPORTAL_CONFIG=../.dev/config.toml \
  ../.venv/bin/python -m stockportal.batch.aggregate --rebuild

# 週次の後続の処理(手動。--only でやり直す手順を選べる)
STOCKPORTAL_CONFIG=../.dev/config.toml \
  ../.venv/bin/python -m stockportal.batch.weekly --as-of 2026-09-25 --only aggregate

# サーバー
STOCKPORTAL_CONFIG=../.dev/config.toml \
  ../.venv/bin/uvicorn stockportal.app:factory --factory --host 127.0.0.1 --port 8765
```

`/api/health` が `{"ok": true}` を返せば動いている。家の外からの接続は 403 になる(§9.1)。

## テスト

```
cd server && ../.venv/bin/python -m pytest tests -q
```

既存のプロジェクトの出力が無い環境では、実物を使うテストは自動で飛ばす。

## まだ作っていないもの

| 機能 | 理由 |
|---|---|
| 主体別売買動向(F1-9)の集計 | J-Quants `/equities/investor-types` が未取得。項目名・`Section` の値・`PubDate` が要確認(詳細設計書 §6.7・§12.4) |
| 日本をとりまく指標(F1-7)の集計 | 財務省・日本銀行・EIA が未取得。系列コード・CSV の形・公表時刻が要確認(同 §6.8・§12.4) |
| 主体別売買動向・指標を使う画面の欄 | 上の2つの集計ができてから表示される。API は理由を添えて空で返し、画面はそのカードだけ「データを読み込めませんでした」を出す |

どちらも `manifest.json` の `sources` に理由を残し、API はそのカードだけを空で返す。
画面はカードごとに「データを読み込めませんでした」を出す(§8.2)。
