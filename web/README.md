# web(画面)

詳細設計書 [docs/detailed-design.md](../docs/detailed-design.md) の §8 の実装。
SvelteKit(`adapter-static`)+ TypeScript + Apache ECharts。

## 画面

| URL | 画面 |
|---|---|
| `/market` | G-11 市場概況 ① 日本市場 |
| `/market/segments` | G-12 市場概況 ② 市場区分 |
| `/market/sectors` | G-13 市場概況 ③ 業種 |
| `/weekly/verdicts` | G-21 手法ごとの判定表 |
| `/weekly/picks` | G-22 来週の買い注文の候補 |
| `/weekly/candidates` | G-23 買い候補(パターン) |
| `/settings` | G-30 設定(色の上書き) |

## 開発

```
npm install
npm run dev        # http://localhost:5173(/api は 8765 のサーバーに回す)
```

サーバーを先に立てておく(`server/README.md`)。

## 書き出し

```
npm run build      # build/ に静的ファイルを書き出す。FastAPI がこれを配る
```

## 検査

```
npm run check      # svelte-check(型)
npm run test       # vitest(書式・絞り込み・株数・コントラスト比)
```

## 色

色はコードに書かない。`/api/theme`(`config.toml` の `[theme]`)を CSS 変数として
`:root` に流し込み、ECharts も `getComputedStyle` で同じ変数から読む。
端末ごとの上書きは `localStorage`(設定画面 G-30)。`src/lib/app.css` の `:root` に
あるのは、API が取れなかったときの保険。

スプリント1はライトモードだけ(基本設計書 §4.8)。
