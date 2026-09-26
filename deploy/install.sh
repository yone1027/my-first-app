#!/bin/zsh
# ポータルを入れる(詳細設計書 §10.3)。
# 使い方: deploy/install.sh [リポジトリのパス]
#
# 何度でも動かせる。動いている版は /Users/yone/StockPortal/app/ に書き出すので、
# 作業中のブランチの変更が混ざらない。

set -eu

REPO=${1:-$(cd "$(dirname "$0")/.." && pwd)}
ROOT=/Users/yone/StockPortal
APP=$ROOT/app
LABELS=(com.yone.stockportal.server com.yone.stockportal.weekly)

say() { print -P "%F{cyan}==>%f $1"; }
warn() { print -P "%F{yellow}!!%f $1"; }

# ---- 手順 0: 初回だけの用意(§10.3 の 0)----
say "初回だけの用意を確かめます"
if ! command -v uv >/dev/null 2>&1; then
  warn "uv がありません。次を実行してください: brew install uv && uv python install 3.12"
  exit 1
fi
if [[ "$(scutil --get LocalHostName 2>/dev/null)" != "stockportal" ]]; then
  warn "スマホから http://stockportal.local:8765 で開けるようにするには、次を実行してください:"
  warn "  sudo scutil --set LocalHostName stockportal"
fi
if ! pmset -g sched 2>/dev/null | grep -q 'wakeorpoweron.*SAT'; then
  warn "土曜 3:00 に Mac が起きているようにするには、次を実行してください:"
  warn "  sudo pmset repeat wakeorpoweron SAT 02:55"
fi

# ---- 手順 1: 動かす版を書き出す ----
say "リポジトリの main を $APP に書き出します"
mkdir -p "$ROOT"/{data/{market,raw,status},logs/weekly}
rm -rf "$APP.new"
mkdir -p "$APP.new"
git -C "$REPO" archive --format=tar main | tar -x -C "$APP.new"

# ---- 手順 2: ポータルの仮想環境 ----
say "server で uv sync します"
(cd "$APP.new/server" && uv sync --quiet)

# ---- 手順 3: 画面を書き出す ----
say "web で npm ci && npm run build します"
(cd "$APP.new/web" && npm ci --silent && npm run build --silent)

# ---- 手順 4: 設定ファイル ----
if [[ ! -f "$ROOT/config.toml" ]]; then
  say "設定ファイルの見本をコピーします($ROOT/config.toml)"
  cp "$APP.new/config/config.example.toml" "$ROOT/config.toml"
else
  say "設定ファイルはそのまま使います($ROOT/config.toml)"
fi

# 入れ替え(途中で失敗しても今の版が残る)
rm -rf "$APP.old"
[[ -d "$APP" ]] && mv "$APP" "$APP.old"
mv "$APP.new" "$APP"
rm -rf "$APP.old"

# ---- 手順 5: launchd ----
say "launchd に登録します"
for label in $LABELS; do
  cp "$APP/deploy/launchd/$label.plist" "$HOME/Library/LaunchAgents/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$label.plist"
done

# ---- 手順 6: 初回だけ、全期間を集計 ----
if [[ ! -f "$ROOT/data/market/manifest.json" ]]; then
  say "初回なので、全期間の集計を作ります(数分かかります)"
  (cd "$APP/server" && STOCKPORTAL_CONFIG=$ROOT/config.toml .venv/bin/python -m stockportal.batch.aggregate --rebuild)
fi

say "入れ終わりました。http://localhost:8765 で開けます"
say "既存の com.yone.technicalanalysis.screen には触っていません"
