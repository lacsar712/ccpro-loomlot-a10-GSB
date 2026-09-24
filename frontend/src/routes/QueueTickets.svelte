<script>
  import { onMount } from 'svelte';
  import { api, QUEUE_STATE, QUEUE_TIMEOUT_MINUTES } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let vats = [];
  let rows = [];
  let error = '';
  let form = { vatId: '' };
  let busy = false;

  const isSupervisor = () => $user?.role === 'admin';

  async function load() {
    error = '';
    try {
      [vats, rows] = await Promise.all([api('/vats'), api('/queue-tickets')]);
      if (!form.vatId && vats.length) form.vatId = String(vats[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function vatLabel(id) {
    const v = vats.find((x) => x.id === id);
    return v ? `${v.vatCode}（${v.fiberType}）` : id;
  }

  function fmt(iso) {
    return iso ? new Date(iso).toLocaleString() : '—';
  }

  function remaining(row) {
    if (row.state !== 'called' || !row.deadlineAt) return '';
    const ms = new Date(row.deadlineAt).getTime() - Date.now();
    const mins = Math.max(0, Math.ceil(ms / 60000));
    return `剩余 ${mins} 分钟`;
  }

  async function take() {
    error = '';
    busy = true;
    try {
      await api('/queue-tickets', {
        method: 'POST',
        body: JSON.stringify({ vatId: Number(form.vatId) }),
      });
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function call(row) {
    error = '';
    busy = true;
    try {
      await api(`/queue-tickets/${row.id}/call`, { method: 'POST' });
      await load();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  // 与看板「等待叫号」同口径：state === waiting 的行。
  $: waitingCount = rows.filter((r) => r.state === 'waiting').length;
</script>

<h1 class="page-title">叫号排队</h1>
<p class="page-sub">
  操作员取号排队，由主管叫号；叫号后 {QUEUE_TIMEOUT_MINUTES}
  分钟内必须开出染程，超时自动作废，作废后需重新取号。未叫号或已作废不得开染程。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >所属染缸
      <select bind:value={form.vatId}>
        {#each vats as v}
          <option value={String(v.id)}>{v.vatCode} · {v.fiberType}</option>
        {/each}
      </select>
    </label>
  </div>
  <div class="toolbar">
    <button class="btn" type="button" disabled={busy} on:click={take}>取号</button>
    <span class="muted">当前等待叫号 <strong>{waitingCount}</strong> 条（同缸同时最多一个在途号）</span>
  </div>
  {#if !isSupervisor()}
    <p class="muted small">叫号仅主管可操作；操作员可取号后等待叫号。</p>
  {/if}
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <table>
    <thead>
      <tr>
        <th>号 ID</th>
        <th>所属染缸</th>
        <th>取号时刻</th>
        <th>叫号时刻</th>
        <th>作废/完成时刻</th>
        <th>取号人</th>
        <th>状态</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{vatLabel(row.vatId)}</td>
          <td>{fmt(row.takenAt)}</td>
          <td>{fmt(row.calledAt)}</td>
          <td>{row.state === 'voided' ? fmt(row.voidedAt) : fmt(row.completedAt)}</td>
          <td>{row.takenBy}</td>
          <td>
            <span class="badge q-{row.state}">{QUEUE_STATE[row.state] || row.state}</span>
            {#if row.state === 'called'}
              <span class="muted small"> · {remaining(row)}</span>
            {/if}
          </td>
          <td class="row-actions">
            {#if row.state === 'waiting' && isSupervisor()}
              <button class="btn small" type="button" disabled={busy} on:click={() => call(row)}
                >叫号</button
              >
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .muted {
    color: var(--indigo-mist);
  }
  .small {
    font-size: 0.78rem;
  }
  .badge.waiting,
  .badge.q-waiting {
    color: #e0a84a;
    border-color: rgba(224, 168, 74, 0.5);
    background: rgba(224, 168, 74, 0.12);
  }
  .badge.q-called {
    color: #8ad8ff;
    border-color: rgba(90, 170, 230, 0.55);
    background: rgba(90, 170, 230, 0.14);
  }
  .badge.q-voided {
    color: #e07a7a;
    border-color: rgba(224, 122, 122, 0.5);
  }
  .badge.q-completed {
    color: var(--ok);
    border-color: rgba(76, 175, 130, 0.45);
  }
</style>
