# my-first-app

Orca × GitHub × アプリ開発の学習用リポジトリです（仮の名前）。

## 概要
J-Quants のデータを中心に、自分好みの株価データと週次の分析結果を見られる自分専用のポータルサイトを作る。
要件は [docs/requirements.md](docs/requirements.md)(草案)を参照。
画面ごとの動きは [docs/basic-design.md](docs/basic-design.md)(基本設計書・草案)を参照。
どう作るか(構成・API・バッチ・ファイルの形)は [docs/detailed-design.md](docs/detailed-design.md)(詳細設計書・草案)を参照。

## 開発の流れ
- `main` ブランチへの直接pushはせず、`feature/xxx` ブランチからPRを作成する
- 1タスク＝1worktree＝1ブランチ

## スプリント1の実装

| 場所 | 中身 |
|---|---|
| [docs/](docs/) | 要件定義書・基本設計書・詳細設計書 |
| [server/](server/) | FastAPI のサーバー、既存の出力のリーダー、市場概況の集計、週次の後続の処理 |
| [web/](web/) | SvelteKit の画面(市場概況3・週次3・設定1) |
| [deploy/](deploy/) | launchd の plist と `install.sh` |
| [config/](config/) | 設定ファイルの見本 |

動かし方は [server/README.md](server/README.md) と [web/README.md](web/README.md)。
実機に入れるときは `deploy/install.sh`。

まだ作っていないもの: 主体別売買動向(F1-9)と日本をとりまく指標(F1-7)の集計。
どちらもデータ元を一度も取得しておらず、項目名や系列コードが要確認のため
(詳細設計書 §6.7・§6.8・§12.4)。
