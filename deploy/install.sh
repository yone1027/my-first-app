#!/bin/zsh
# ポータルを入れる(詳細設計書 §10.3)。
# 使い方: deploy/install.sh [リポジトリのパス]
#
# 何度でも動かせる。動いている版は /Users/yone/StockPortal/app/ に書き出すので、
# 作業中のブランチの変更が混ざらない。

set -eu

REPO=${1:-$(cd "$(dirname "$0")/.." && pwd)}
REF=${2:-origin/main}
ROOT=/Users/yone/StockPortal
APP=$ROOT/app
LABELS=(com.yone.stockportal.server com.yone.stockportal.weekly)

say() { print -P "%F{cyan}==>%f $1"; }
warn() { print -P "%F{yellow}!!%f $1"; }
die() { print -P "%F{red}××%f $1"; exit 1; }

# 途中で失敗したら、書きかけを片付ける(今動いている版はそのまま残す)
cleanup() { rm -rf "$APP.new"; }
trap cleanup EXIT

# ---- 手順 0: 初回だけの用意(§10.3 の 0)----
say "初回だけの用意を確かめます"
# ~/.local/bin(公式インストーラーの置き場所)も見る
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  warn "uv がありません。次を実行してください:"
  warn "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  warn "  uv python install 3.12"
  warn "(brew install uv は使わない。bottle が無くソースからビルドになる。詳細設計書 §2.1)"
  exit 1
fi
if [[ "$(scutil --get LocalHostName 2>/dev/null)" != "stockportal" ]]; then
  warn "スマホから http://stockportal.local:8765 で開けるようにするには、次を実行してください:"
  warn "  sudo scutil --set LocalHostName stockportal"
fi
# `pmset -g sched` の出力は "wakepoweron at 2:55AM Saturday"(type 名と綴りが違う)
if ! pmset -g sched 2>/dev/null | grep -qi 'wakepoweron.*saturday'; then
  warn "土曜 3:00 に Mac が起きているようにするには、次を実行してください:"
  warn "  sudo pmset repeat wakeorpoweron S 02:55:00"   # 曜日は MTWRFSU の部分集合、時刻は HH:mm:ss
fi

# ---- 手順 1: 動かす版を書き出す ----
# 既定は origin/main。ローカルの main は古いことがあるので、既定では使わない。
# 別の版を入れるときは第2引数で渡す(例: deploy/install.sh "$PWD" develop)。
git -C "$REPO" rev-parse --verify --quiet "$REF" >/dev/null \
  || die "$REF が見つかりません。git fetch してから、もう一度実行してください"
git -C "$REPO" cat-file -e "$REF:server/pyproject.toml" 2>/dev/null \
  || die "$REF に server/ がありません($(git -C "$REPO" log --oneline -1 "$REF"))。書き出す版を確かめてください"

say "$REF($(git -C "$REPO" log --oneline -1 "$REF"))を $APP に書き出します"
mkdir -p "$ROOT"/{data/{market,raw,status},logs/weekly}
rm -rf "$APP.new"
mkdir -p "$APP.new"
git -C "$REPO" archive --format=tar "$REF" | tar -x -C "$APP.new"
for needed in server/pyproject.toml web/package.json config/config.example.toml; do
  [[ -f "$APP.new/$needed" ]] || die "書き出しに $needed が入っていません"
done

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
trap - EXIT   # ここまで来たら片付けない

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
