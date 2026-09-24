<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, QUEUE_STATE, QUEUE_TIMEOUT_MINUTES, toLocalInput, fromLocalInput } from '../lib/api.js';

  let vats = [];
  let rows = [];
  let tickets = [];
  let error = '';
  let form = {
    vatId: '',
    recipeName: '',
    fabricKg: 20,
    startedAt: toLocalInput(new Date().toISOString()),
    operatorName: '染程操作员',
  };
  let editing = null;

  async function load() {
    error = '';
    try {
      [vats, rows, tickets] = await Promise.all([
        api('/vats'),
        api('/dye-lots'),
        api('/queue-tickets'),
      ]);
      const usable = vats.filter((v) => v.status === 'ready' || v.status === 'dyeing');
      if (!form.vatId && usable.length) form.vatId = String(usable[0].id);
      else if (!form.vatId && vats.length) form.vatId = String(vats[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  // 所选染缸当前在途号（未作废未完成，可能已超时）。
  $: selectedTicket = tickets.find((t) => String(t.vatId) === String(form.vatId) &&
    (t.state === 'waiting' || t.state === 'called'));
  $: canOpen = selectedTicket?.state === 'called';

  function vatLabel(id) {
    const v = vats.find((x) => x.id === id);
    if (!v) return id;
    return `${v.vatCode}（${VAT_STATUS[v.status] || v.status}）`;
  }

  async function save() {
    error = '';
    try {
      const body = {
        vatId: Number(form.vatId),
        recipeName: form.recipeName.trim(),
        fabricKg: Number(form.fabricKg),
        startedAt: fromLocalInput(form.startedAt),
        operatorName: form.operatorName.trim(),
      };
      if (editing) {
        await api(`/dye-lots/${editing}`, { method: 'PUT', body: JSON.stringify(body) });
      } else {
        await api('/dye-lots', { method: 'POST', body: JSON.stringify(body) });
      }
      editing = null;
      form = {
        ...form,
        recipeName: '',
        fabricKg: 20,
        startedAt: toLocalInput(new Date().toISOString()),
      };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(row) {
    editing = row.id;
    form = {
      vatId: String(row.vatId),
      recipeName: row.recipeName,
      fabricKg: row.fabricKg,
      startedAt: toLocalInput(row.startedAt),
      operatorName: row.operatorName,
    };
  }

  async function remove(id) {
    if (!confirm('确认删除该染程？')) return;
    error = '';
    try {
      await api(`/dye-lots/${id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">染程</h1>
<p class="page-sub">
  开缸须先在「叫号排队」取号并经主管叫号；未叫号或已作废会被 409 拦截。叫号后 {QUEUE_TIMEOUT_MINUTES}
  分钟内必须开出染程，超时号自动作废。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >染缸
      <select bind:value={form.vatId}>
        {#each vats as v}
          <option value={String(v.id)}
            >{v.vatCode} · {VAT_STATUS[v.status] || v.status} · {v.fiberType}</option
          >
        {/each}
      </select>
    </label>
    <label>配方名 <input bind:value={form.recipeName} /></label>
    <label>布料 kg <input type="number" step="0.1" bind:value={form.fabricKg} /></label>
    <label>开始时间 <input type="datetime-local" bind:value={form.startedAt} /></label>
    <label>操作员 <input bind:value={form.operatorName} /></label>
  </div>

  {#if selectedTicket}
    <p class="ticket-hint {selectedTicket.state}">
      当前号 #{selectedTicket.id}：{QUEUE_STATE[selectedTicket.state] || selectedTicket.state}
      {#if selectedTicket.state === 'waiting'}— 请等待主管叫号后再开染程{/if}
      {#if selectedTicket.state === 'called' && selectedTicket.deadlineAt}
        — 须在 {new Date(selectedTicket.deadlineAt).toLocaleTimeString()} 前开出染程
      {/if}
    </p>
  {:else}
    <p class="ticket-hint voided">该染缸无有效叫号，请先到「叫号排队」取号并等待叫号。</p>
  {/if}

  <div class="toolbar">
    <button class="btn" type="button" disabled={!editing && !canOpen} on:click={save}
      >{editing ? '保存修改' : '新建染程'}</button
    >
    {#if editing}
      <button class="btn ghost" type="button" on:click={() => (editing = null)}>取消</button>
    {/if}
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染缸</th>
        <th>配方</th>
        <th>布料 kg</th>
        <th>开始</th>
        <th>操作员</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{vatLabel(row.vatId)}</td>
          <td>{row.recipeName}</td>
          <td>{row.fabricKg}</td>
          <td>{new Date(row.startedAt).toLocaleString()}</td>
          <td>{row.operatorName}</td>
          <td class="row-actions">
            <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>编辑</button>
            <button class="btn danger small" type="button" on:click={() => remove(row.id)}>删除</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .ticket-hint {
    margin: 0 0 0.75rem;
    font-size: 0.85rem;
  }
  .ticket-hint.waiting {
    color: #e0a84a;
  }
  .ticket-hint.called {
    color: #8ad8ff;
  }
  .ticket-hint.voided {
    color: #e07a7a;
  }
</style>
