<script lang="ts">
  /** G-24 週次 推奨銘柄の成績(基本設計書 §5.8)。
   *  過去の「来週の推奨銘柄」が、指値で買えたか・目標と損切りのどちらに届いたか。
   *  件数を数えるだけで、点数や順位は出さない(R1・R2・R5)。 */
  import Cautions from '$lib/components/Cautions.svelte';
  import CardState from '$lib/components/CardState.svelte';
  import WeeklyTabs from '$lib/components/WeeklyTabs.svelte';
  import { api, ApiFailure, type Dates, type Evaluation, type Outcome } from '$lib/api';
  import { dateWithWeekday, int, price, ratioPct, stamp } from '$lib/format';
  import { OUTCOME_COLOR, outcomeText } from '$lib/labels';

  let dates = $state<Dates | null>(null);
  let data = $state<Evaluation | null>(null);
  let failure = $state<string | null>(null);

  $effect(() => {
    api.dates().then((d) => (dates = d)).catch(() => (dates = null));
    api
      .evaluation()
      .then((body) => {
        data = body;
        failure = null;
      })
      .catch((e: ApiFailure) => {
        data = null;
        failure = e.body?.error === 'no_data' ? 'まだ成績がありません(土曜のバッチで作られます)' : `読み込みに失敗しました(${e.status})`;
      });
  });

  const s = $derived(data?.summary);

  /** 決済の欄。保有中は直近の終値の日を出す。 */
  function exitText(r: Outcome): string {
    if (r.status === 'holding') return r.last_date ? `${shortDate(r.last_date)} 時点(終値 ${price(r.last_close)})` : '—';
    if (!r.exit_date) return '—';
    return `${shortDate(r.exit_date)} ${price(r.exit_price)}`;
  }

  function shortDate(iso: string): string {
    return dateWithWeekday(iso).slice(5);
  }
</script>

<WeeklyTabs {dates} date="" tab="evaluation" counts={{ evaluation: data?.rows.length ?? null }} />
<CardState error={failure} />

{#if data && s}
  <section class="card">
    <h2>集計</h2>
    <p class="sub">{dateWithWeekday(data.as_of)} までの日足で判定 / 作成 {stamp(data.generated_at)}</p>
    <div class="stats">
      <div><span class="k">推奨銘柄</span><span class="v">{int(s.total)} 件</span></div>
      <div>
        <span class="k">約定</span>
        <span class="v">{int(s.filled)} / {int(s.decided)} 件</span>
        <span class="sub">{ratioPct(s.fill_rate)}</span>
      </div>
      <div>
        <span class="k">勝ち</span>
        <span class="v" style:color="var(--up)">{int(s.count.win)} 件</span>
        <span class="sub">目標 {s.reasons.win.target} / 期限 {s.reasons.win.time}</span>
      </div>
      <div>
        <span class="k">負け</span>
        <span class="v" style:color="var(--down)">{int(s.count.lose)} 件</span>
        <span class="sub">損切り {s.reasons.lose.stop} / 期限 {s.reasons.lose.time}</span>
      </div>
      <div><span class="k">保有中</span><span class="v">{int(s.count.holding)} 件</span></div>
      <div>
        <span class="k">未約定 / 注文中</span>
        <span class="v">{int(s.count.unfilled)} / {int(s.count.ordering)} 件</span>
      </div>
      <div>
        <span class="k">決済した注文の平均リターン</span>
        <span class="v">{ratioPct(s.mean_ret, 1, true)}</span>
        <span class="sub">{int(s.settled)} 件</span>
      </div>
    </div>

    <h3>予測と実際</h3>
    <div class="scroll-x">
      <table>
        <thead><tr><th></th><th class="num">予測(平均)</th><th class="num">実際</th><th class="num">対象</th></tr></thead>
        <tbody>
          <tr><th>指値まで下がる(約定)</th><td class="num">{ratioPct(s.predicted_fill)}</td><td class="num">{ratioPct(s.fill_rate)}</td><td class="num">{int(s.decided)} 件</td></tr>
          <tr><th>約定後に目標に届く</th><td class="num">{ratioPct(s.predicted_target)}</td><td class="num">{ratioPct(s.actual_target)}</td><td class="num">{int(s.settled)} 件</td></tr>
          <tr><th>約定後に損切りに届く</th><td class="num">{ratioPct(s.predicted_stop)}</td><td class="num">{ratioPct(s.actual_stop)}</td><td class="num">{int(s.settled)} 件</td></tr>
        </tbody>
      </table>
    </div>

    <ul class="notes">
      <li>件数が少ないうちは、偶然の影響がとても大きい。予測と実際の差だけで、良し悪しは決められない</li>
      <li>値段は画面(md)に出ている指値・損切り・目標。リターンは手数料を含まない</li>
      <li>同じ日に目標と損切りの両方に届いたときは損切りとする。約定した日は損切りだけを見る(既存の検証と同じ)</li>
      <li>どちらにも届かなければ、約定から20営業日目の終値で売る。そのときはプラスなら勝ち、そうでなければ負け</li>
    </ul>
    <Cautions />
  </section>

  <section class="card">
    <h2>銘柄ごとの結果</h2>
    <div class="scroll-x">
      <table>
        <thead>
          <tr>
            <th>基準日</th><th>銘柄</th>
            <th class="num">指値</th><th class="num">損切り</th><th class="num">目標</th>
            <th>結果</th><th>約定</th><th>決済</th><th class="num">リターン</th>
          </tr>
        </thead>
        <tbody>
          {#each data.rows as r (r.date + r.code)}
            <tr>
              <td>{shortDate(r.date)}</td>
              <td><a href={`/weekly/picks?date=${r.date}`}>{r.code} {r.name ?? ''}</a></td>
              <td class="num">{price(r.entry)}</td>
              <td class="num">{price(r.stop)}</td>
              <td class="num">{price(r.target)}</td>
              <td style:color={OUTCOME_COLOR[r.status]} title={r.note ?? ''}><strong>{outcomeText(r.status, r.reason)}</strong></td>
              <td>{r.fill_date ? `${shortDate(r.fill_date)} ${price(r.fill_price)}` : '—'}</td>
              <td>{exitText(r)}</td>
              <td class="num">
                {ratioPct(r.ret, 1, true)}{#if r.status === 'holding'}<span class="muted">(含み)</span>{/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
{/if}

<style>
  .stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin: 12px 0; }
  .stats > div { display: flex; flex-direction: column; gap: 2px; }
  .stats .k { font-size: 12px; color: var(--text-sub); }
  .stats .v { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .notes { color: var(--text-sub); font-size: 13px; padding-left: 1.2em; }
  td { white-space: nowrap; }
</style>
