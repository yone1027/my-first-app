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
| ドル円(F1-7 の一部) | **取得元が未定。** 日本銀行は直接取得できる CSV を公開しておらず(直近70営業日の PDF と、フォーム操作前提の検索サイトのみ)、財務省にも日次のドル円はない(2026-09-27 に調査。詳細設計書 §6.8) |
| WTI 原油(F1-7 の一部) | **EIA の無料 API キーが未設定。** https://www.eia.gov/opendata/register.php で取得し、`/Users/yone/StockPortal/.env` に `EIA_API_KEY=…` として置く |

取れていない指標は `manifest.json` の `sources` に理由を残し、API はその指標だけ空で返す。
画面はそのカードだけに理由を出す(他のカードは出る)。

主体別売買動向(F1-9)と10年国債利回りは **2026-09-27 に実装済み**。

どちらも `manifest.json` の `sources` に理由を残し、API はそのカードだけを空で返す。
画面はカードごとに「データを読み込めませんでした」を出す(§8.2)。
