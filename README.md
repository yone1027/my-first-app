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
