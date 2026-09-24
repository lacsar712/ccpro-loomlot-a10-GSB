<script>
  import { onMount, onDestroy } from 'svelte';
  import { api, QUEUE_STATUS, QUEUE_TIMEOUT_MINUTES } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let vats = [];
  let houses = [];
  let rows = [];
  let error = '';
  let showAll = false;
  let form = { vatId: '', takenBy: '' };
  let nowTick = Date.now();
  let ticker;

  $: isAdmin = $user?.role === 'admin';

  async function load() {
    error = '';
    try {
      const scope = showAll ? 'all' : 'active';
      const [ticketData, vatData, houseData] = await Promise.all([
        api(`/queue?scope=${scope}`),
        api('/vats'),
        api('/dye-houses'),
      ]);
      rows = ticketData;
      vats = vatData;
      houses = houseData;
      if (!form.vatId && vats.length) form.vatId = String(vats[0].id);
      if (!form.takenBy) form.takenBy = $user?.displayName || '';
    } catch (e) {
      error = e.message;
    }
  }

  onMount(async () => {
    await load();
    ticker = setInterval(() => (nowTick = Date.now()), 1000);
  });

  onDestroy(() => clearInterval(ticker));

  function houseName(id) {
    return houses.find((h) => h.id === id)?.name || '';
  }

  function remainText(expiresAt) {
    if (!expiresAt) return '';
    const ms = new Date(expiresAt).getTime() - nowTick;
    if (ms <= 0) return '已超时（刷新后作废）';
    const m = Math.floor(ms / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    return `剩余 ${m} 分 ${String(s).padStart(2, '0')} 秒`;
  }

  // 倒计时归零后刷新，触发后端超时作废判定
  $: if (nowTick) {
    const hit = rows.some(
      (r) => r.status === 'called' && r.expiresAt && new Date(r.expiresAt).getTime() <= nowTick
    );
    if (hit) load();
  }

  async function take() {
    error = '';
    try {
      await api('/queue/take', {
        method: 'POST',
        body: JSON.stringify({
          vatId: Number(form.vatId),
          takenBy: form.takenBy.trim() || ($user?.displayName ?? ''),
        }),
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function call(id) {
    error = '';
    try {
      await api(`/queue/${id}/call`, { method: 'POST' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">叫号排队</h1>
<p class="page-sub">
  操作员可取号；叫号仅主管。叫号后 <strong>{QUEUE_TIMEOUT_MINUTES} 分钟</strong>
  内必须开出染程，超时该号自动作废；未叫号或已作废开染程将被拒绝（409）。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >染缸
      <select bind:value={form.vatId}>
        {#each vats as v}
          <option value={String(v.id)}
            >{v.vatCode} · {houseName(v.dyeHouseId)} · {v.fiberType}</option
          >
        {/each}
      </select>
    </label>
    <label>取号人 <input bind:value={form.takenBy} maxlength="64" /></label>
  </div>
  <div class="toolbar">
    <button class="btn" type="button" on:click={take}>取号</button>
    <span style="font-size:0.8rem;color:var(--indigo-mist);">
      同一染缸未作废且未完成的号同时最多一个
    </span>
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <div class="toolbar">
    <label style="font-size:0.85rem;display:flex;align-items:center;gap:0.4rem;">
      <input type="checkbox" bind:checked={showAll} on:change={load} />
      显示全部历史号（含已完成 / 已作废）
    </label>
  </div>
  <table>
    <thead>
      <tr>
        <th>号</th>
        <th>染坊 / 染缸</th>
        <th>取号人</th>
        <th>取号时刻</th>
        <th>叫号时刻</th>
        <th>状态</th>
        <th>时限</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{row.houseName} · {row.vatCode}</td>
          <td>{row.takenBy}</td>
          <td>{new Date(row.takenAt).toLocaleString()}</td>
          <td>{row.calledAt ? new Date(row.calledAt).toLocaleString() : '—'}</td>
          <td>
            <span class="badge q-{row.status}">{QUEUE_STATUS[row.status] || row.status}</span>
            {#if row.voidedAt}
              <div class="sub">{new Date(row.voidedAt).toLocaleString()} 作废</div>
            {/if}
            {#if row.completedAt}
              <div class="sub">{new Date(row.completedAt).toLocaleString()} 完成</div>
            {/if}
          </td>
          <td>
            {#if row.status === 'called'}
              <span class="countdown">{remainText(row.expiresAt)}</span>
            {:else}
              —
            {/if}
          </td>
          <td class="row-actions">
            {#if row.status === 'taken' && isAdmin}
              <button class="btn small" type="button" on:click={() => call(row.id)}>叫号</button>
            {:else if row.status === 'taken' && !isAdmin}
              <span class="sub">待主管叫号</span>
            {/if}
          </td>
        </tr>
      {/each}
      {#if rows.length === 0}
        <tr><td colspan="8" class="sub" style="text-align:center;padding:1.2rem;">暂无排队号</td></tr>
      {/if}
    </tbody>
  </table>
</div>

<style>
  .sub {
    font-size: 0.72rem;
    color: var(--indigo-mist);
    margin-top: 0.15rem;
  }

  .countdown {
    font-size: 0.78rem;
    color: var(--warn);
    white-space: nowrap;
  }

  .badge.q-taken {
    color: #ffd98a;
    border-color: rgba(224, 168, 74, 0.5);
    background: rgba(224, 168, 74, 0.12);
  }

  .badge.q-called {
    color: #b8a8ff;
    border-color: rgba(107, 92, 231, 0.55);
    background: rgba(107, 92, 231, 0.15);
  }

  .badge.q-completed {
    color: var(--ok);
    border-color: rgba(76, 175, 130, 0.45);
  }

  .badge.q-voided {
    color: var(--warn);
    border-color: rgba(224, 168, 74, 0.45);
  }
</style>
