<script>
  import { goto } from '$app/navigation';

  let batches = $state([]);
  let loading = $state(true);
  let processing = $state(false);
  let activeBatch = $state(null);
  let logs = $state([]);
  let pollTimer = $state(null);
  let errorItems = $state({});
  let expandedErrors = $state({});
  let retrying = $state(false);
  let showTerminal = $state(false);
  let expandedBatch = $state(null);
  let expandedData = $state([]);

  const api = {
    async getQueueBatches() { const r = await fetch('/api/queue/batches'); return r.json(); },
    async processQueue(bid = null) { const r = await fetch(bid ? `/api/process/background?batch_id=${bid}` : '/api/process/background', { method: 'POST' }); if (!r.ok) { const e = await r.json().catch(() => ({ detail: 'Failed' })); throw new Error(e.detail); } return r.json(); },
    async getQueueStatus(bid = null) { const r = await fetch(bid ? `/api/queue?batch_id=${bid}` : '/api/queue'); return r.json(); },
    async getQueueErrors(bid = null) { const r = await fetch(bid ? `/api/queue/errors?batch_id=${bid}` : '/api/queue/errors'); return r.ok ? r.json() : []; },
    async retryItem(qid) { const r = await fetch(`/api/queue/retry/${qid}`, { method: 'POST' }); if (!r.ok) throw new Error('Retry failed'); return r.json(); }
  };

  async function fetchBatches() { loading = true; try { batches = await api.getQueueBatches(); } catch (e) { log(`ERROR: ${e.message}`); } finally { loading = false; } }
  function log(msg) { const ts = new Date().toLocaleTimeString('en-US', { hour12: false }); logs = [...logs, `[${ts}] ${msg}`]; showTerminal = true; }

  async function processAll() { processing = true; activeBatch = null; log('Processing all pending...'); try { await api.processQueue(); startPolling(); } catch (e) { log(`ERROR: ${e.message}`); processing = false; } }
  async function processBatch(bid) { processing = true; activeBatch = bid; log(`Processing [${bid}]...`); try { await api.processQueue(bid); startPolling(bid); } catch (e) { log(`ERROR: ${e.message}`); processing = false; activeBatch = null; } }

  function startPolling(bid = null) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      const status = await api.getQueueStatus(bid);
      const items = Array.isArray(status) ? status : [status];
      const pending = items.filter(i => i.status === 'pending').length;
      log(`${items.filter(i=>i.status==='done').length} done, ${pending} pending`);
      await fetchBatches();
      if (pending === 0) { clearInterval(pollTimer); pollTimer = null; log('Complete.'); processing = false; activeBatch = null; }
    }, 3000);
  }

  async function toggleErrors(bid) {
    if (expandedErrors[bid]) { expandedErrors = { ...expandedErrors, [bid]: false }; return; }
    const items = await api.getQueueErrors(bid);
    errorItems = { ...errorItems, [bid]: items };
    expandedErrors = { ...expandedErrors, [bid]: true };
  }
  async function retryItem(qid, bid) { retrying = true; try { await api.retryItem(qid); log(`Retried #${qid}`); errorItems = { ...errorItems, [bid]: await api.getQueueErrors(bid) }; await fetchBatches(); } catch (e) { log(e.message); } finally { retrying = false; } }
  async function retryAllErrors(bid) { retrying = true; for (const i of (errorItems[bid]||[])) { try { await api.retryItem(i.id); } catch(_){} } errorItems = { ...errorItems, [bid]: await api.getQueueErrors(bid) }; await fetchBatches(); retrying = false; }

  function tryParse(val) {
    if (!val) return val;
    if (typeof val === 'string') { try { return JSON.parse(val); } catch { return val; } }
    return val;
  }

  async function toggleExpand(bid) {
    if (expandedBatch === bid) { expandedBatch = null; expandedData = []; return; }
    try {
      const r = await fetch(`/api/data?folder=${bid}`);
      const raw = await r.json();
      expandedData = raw.map(d => ({
        ...d,
        products: tryParse(d.products) || [],
        contact: tryParse(d.contact) || {},
        key_info: tryParse(d.key_info) || []
      }));
    } catch (e) {
      expandedData = [];
      log(`ERROR loading data: ${e.message}`);
    }
    expandedBatch = bid;
  }

  $effect(() => { fetchBatches(); return () => { if (pollTimer) clearInterval(pollTimer); }; });
  function totalPending() { return batches.reduce((s, b) => s + (b.pending ?? 0), 0); }
</script>

<svelte:head><title>QUEUE | KONTACT</title></svelte:head>

<div class="q-page">
  <div class="q-header">
    <div class="q-title-row">
      <h1>QUEUE</h1>
      <span class="q-count">{batches.length} batches · {batches.reduce((s,b) => s + (b.done??0) + (b.pending??0) + (b.errors??0), 0)} images</span>
    </div>
    <div class="q-actions">
      <button class="q-btn q-btn-outline" onclick={fetchBatches} disabled={loading}>{loading ? '...' : 'REFRESH'}</button>
      {#if totalPending() > 0}
        <button class="q-btn q-btn-primary" onclick={processAll} disabled={processing}>{processing ? 'PROCESSING...' : `PROCESS ALL (${totalPending()})`}</button>
      {/if}
    </div>
  </div>

  {#if batches.length === 0 && !loading}
    <div class="q-empty">
      <p>No batches yet</p>
      <button class="q-btn q-btn-primary" onclick={() => goto('/upload')}>UPLOAD IMAGES</button>
    </div>
  {:else}
    <div class="q-list">
      {#each batches as batch (batch.batch_id)}
        {@const total = (batch.done ?? 0) + (batch.pending ?? 0) + (batch.errors ?? 0)}
        {@const pct = total > 0 ? Math.round(((batch.done ?? 0) / total) * 100) : 0}
        <div class="q-row">
          <div class="q-row-main">
            <div class="q-row-left">
              <span class="q-row-icon" class:q-complete={pct === 100} class:q-active={processing && activeBatch === batch.batch_id}>
                {#if processing && activeBatch === batch.batch_id}
                  <span class="q-spinner"></span>
                {:else if pct === 100}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-5"/></svg>
                {:else}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>
                {/if}
              </span>
              <div class="q-row-info">
                <span class="q-row-name">{batch.batch_id}</span>
                <span class="q-row-detail">{total} images · {pct}% done</span>
              </div>
            </div>
            <div class="q-row-right">
              <div class="q-tags">
                {#if (batch.done ?? 0) > 0}<span class="q-tag q-tag-done">{batch.done} done</span>{/if}
                {#if (batch.pending ?? 0) > 0}<span class="q-tag q-tag-pending">{batch.pending} pending</span>{/if}
                {#if (batch.errors ?? 0) > 0}<span class="q-tag q-tag-error">{batch.errors} errors</span>{/if}
              </div>
              <div class="q-row-btns">
                {#if (batch.pending ?? 0) > 0}
                  <button class="q-btn-sm q-btn-primary" onclick={() => processBatch(batch.batch_id)} disabled={processing}>PROCESS</button>
                {/if}
                {#if (batch.errors ?? 0) > 0}
                  <button class="q-btn-sm q-btn-error" onclick={() => toggleErrors(batch.batch_id)}>{expandedErrors[batch.batch_id] ? 'HIDE' : 'ERRORS'}</button>
                {/if}
                <button class="q-btn-sm q-btn-outline" onclick={() => toggleExpand(batch.batch_id)}>{expandedBatch === batch.batch_id ? 'COLLAPSE' : 'EXPAND'}</button>
              </div>
            </div>
          </div>
          <!-- Progress bar -->
          <div class="q-progress"><div class="q-progress-fill" style="width:{pct}%"></div></div>

          <!-- Error items -->
          {#if expandedErrors[batch.batch_id] && errorItems[batch.batch_id]?.length}
            <div class="q-errors">
              <div class="q-errors-head">
                <span class="q-tag q-tag-error">FAILED</span>
                <button class="q-btn-sm q-btn-error" onclick={() => retryAllErrors(batch.batch_id)} disabled={retrying}>RETRY ALL</button>
              </div>
              {#each errorItems[batch.batch_id] as item}
                <div class="q-error-row">
                  <span class="q-error-name">{item.file_name}</span>
                  <span class="q-error-msg">{item.error || 'Unknown'}</span>
                  <button class="q-btn-sm q-btn-error" onclick={() => retryItem(item.id, batch.batch_id)} disabled={retrying}>RETRY</button>
                </div>
              {/each}
            </div>
          {/if}

          <!-- Expanded detail panel -->
          {#if expandedBatch === batch.batch_id}
            <div class="q-expand">
              {#if expandedData.length === 0}
                <div class="q-expand-empty">No documents found for this batch.</div>
              {:else}
                {#each expandedData as doc, i}
                  <div class="q-doc-row">
                    <div class="q-doc-thumb">
                      <div class="q-thumb-skeleton"></div>
                      <img
                        src={`/api/image/${doc.folder}/${doc.source_file}`}
                        alt={doc.source_file}
                        loading="lazy"
                        onload={(e) => { e.target.style.opacity = '1'; e.target.previousElementSibling.style.display = 'none'; }}
                        onerror={(e) => { e.target.style.display = 'none'; e.target.previousElementSibling.style.background = '#ddd'; }}
                      />
                    </div>
                    <div class="q-doc-meta">
                      <div class="q-doc-top">
                        <span class="q-doc-filename">{doc.source_file}</span>
                        {#if doc.image_type}
                          <span class="q-tag q-tag-type">{doc.image_type}</span>
                        {/if}
                      </div>
                      {#if doc.title}
                        <div class="q-doc-title">{doc.title}</div>
                      {/if}
                      {#if doc.products && doc.products.length > 0}
                        <div class="q-doc-products">
                          {doc.products.slice(0, 5).map(p => typeof p === 'string' ? p : (p.name || p.product_name || '')).filter(Boolean).join(', ')}
                          {#if doc.products.length > 5}
                            <span class="q-doc-more">+{doc.products.length - 5} more</span>
                          {/if}
                        </div>
                      {/if}
                      {#if doc.company}
                        <div class="q-doc-company">{typeof doc.company === 'string' ? doc.company : (doc.company.name || doc.company.company_name || '')}</div>
                      {/if}
                      {#if doc.contact}
                        <div class="q-doc-contact">
                          {#if doc.contact.phone}{doc.contact.phone}{/if}
                          {#if doc.contact.phone && doc.contact.email} · {/if}
                          {#if doc.contact.email}{doc.contact.email}{/if}
                        </div>
                      {/if}
                    </div>
                  </div>
                  {#if i < expandedData.length - 1}
                    <div class="q-doc-sep"></div>
                  {/if}
                {/each}
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <!-- Compact terminal log -->
  {#if logs.length > 0}
    <div class="q-terminal">
      <div class="q-terminal-head">
        <span class="q-terminal-title">$ terminal</span>
        <button class="q-terminal-clear" onclick={() => { logs = []; showTerminal = false; }}>CLEAR</button>
      </div>
      <div class="q-terminal-body">
        {#each logs.slice(-8) as line}
          <div class="q-terminal-line">{line}</div>
        {/each}
        {#if processing}<div class="q-terminal-line q-blink">_ processing...</div>{/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .q-page { width:100%; padding:16px; font-family:'Space Grotesk',sans-serif; }

  .q-header { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:20px; flex-wrap:wrap; }
  .q-title-row { display:flex; flex-direction:column; gap:2px; }
  .q-title-row h1 { margin:0; font-size:1.4rem; font-weight:900; letter-spacing:0.08em; }
  .q-count { font-size:0.7rem; color:var(--color-on-surface-dim); letter-spacing:0.04em; text-transform:uppercase; }
  .q-actions { display:flex; gap:6px; }

  /* Buttons */
  .q-btn { font-family:inherit; font-size:0.7rem; font-weight:700; padding:6px 14px; text-transform:uppercase; letter-spacing:0.06em; cursor:pointer; border:2px solid var(--color-on-surface); min-height:32px; }
  .q-btn:disabled { opacity:0.4; cursor:not-allowed; }
  .q-btn-primary { background:var(--color-on-surface); color:var(--color-surface); }
  .q-btn-primary:hover:not(:disabled) { background:var(--color-primary); border-color:var(--color-primary); }
  .q-btn-outline { background:none; color:var(--color-on-surface); }
  .q-btn-outline:hover:not(:disabled) { background:var(--color-on-surface); color:var(--color-surface); }

  .q-btn-sm { font-family:inherit; font-size:0.6rem; font-weight:700; padding:3px 10px; text-transform:uppercase; letter-spacing:0.06em; cursor:pointer; border:1.5px solid var(--color-on-surface); min-height:26px; background:none; color:var(--color-on-surface); }
  .q-btn-sm:hover:not(:disabled) { background:var(--color-on-surface); color:var(--color-surface); }
  .q-btn-sm:disabled { opacity:0.4; cursor:not-allowed; }
  .q-btn-sm.q-btn-primary { background:var(--color-on-surface); color:var(--color-surface); }
  .q-btn-sm.q-btn-error { border-color:#dc2626; color:#dc2626; }
  .q-btn-sm.q-btn-error:hover:not(:disabled) { background:#dc2626; color:#fff; }

  /* List */
  .q-list { display:flex; flex-direction:column; gap:0; }
  .q-row { border:2px solid var(--color-on-surface); border-bottom:none; padding:0; }
  .q-row:last-child { border-bottom:2px solid var(--color-on-surface); }
  .q-row:nth-child(even) { background:var(--color-surface-dim); }

  .q-row-main { display:flex; justify-content:space-between; align-items:center; padding:12px 14px; gap:12px; }
  .q-row-left { display:flex; align-items:center; gap:10px; min-width:0; }
  .q-row-icon { flex-shrink:0; width:20px; height:20px; display:flex; align-items:center; justify-content:center; }
  .q-row-info { display:flex; flex-direction:column; gap:1px; min-width:0; }
  .q-row-name { font-weight:700; font-size:0.85rem; font-family:'Space Grotesk',monospace; }
  .q-row-detail { font-size:0.6rem; color:var(--color-on-surface-dim); text-transform:uppercase; letter-spacing:0.04em; }

  .q-row-right { display:flex; align-items:center; gap:8px; flex-shrink:0; }
  .q-tags { display:flex; gap:4px; }
  .q-row-btns { display:flex; gap:4px; }

  /* Tags */
  .q-tag { font-size:0.55rem; font-weight:900; letter-spacing:0.06em; text-transform:uppercase; padding:2px 6px; }
  .q-tag-done { background:#dcfce7; color:#166534; }
  .q-tag-pending { background:#fef9c3; color:#854d0e; }
  .q-tag-error { background:#fee2e2; color:#991b1b; }
  .q-tag-type { background:var(--color-surface-dim); color:var(--color-on-surface-dim); border:1px solid var(--color-on-surface); }

  /* Progress */
  .q-progress { height:3px; background:var(--color-surface-dim); }
  .q-progress-fill { height:100%; background:var(--color-primary); transition:width 0.4s ease; }

  /* Spinner */
  .q-spinner { width:14px; height:14px; border:2px solid rgba(0,0,0,0.1); border-top-color:var(--color-primary); border-radius:50% !important; animation:qspin 0.7s linear infinite; display:block; }
  @keyframes qspin { to { transform:rotate(360deg); } }

  /* Errors */
  .q-errors { padding:8px 14px; background:#fef2f2; border-top:1px dashed rgba(0,0,0,0.1); }
  .q-errors-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
  .q-error-row { display:flex; align-items:center; gap:8px; padding:4px 0; border-bottom:1px solid rgba(0,0,0,0.06); font-size:0.75rem; }
  .q-error-name { font-family:monospace; font-weight:700; font-size:0.7rem; min-width:0; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .q-error-msg { font-size:0.6rem; color:#991b1b; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; word-break:break-word; max-width:100%; }
  @media (max-width:640px) { .q-error-msg { white-space:normal; max-width:calc(100vw - 120px); } .q-error-row { flex-wrap:wrap; } }

  /* Expanded detail panel */
  .q-expand { border-top:2px dashed var(--color-on-surface); padding:12px 14px; background:var(--color-surface); }
  .q-expand-empty { font-size:0.75rem; color:var(--color-on-surface-dim); text-transform:uppercase; letter-spacing:0.04em; padding:8px 0; }

  .q-doc-row { display:flex; gap:12px; align-items:flex-start; padding:8px 0; }
  .q-doc-thumb { flex-shrink:0; width:60px; height:60px; overflow:hidden; border:1.5px solid var(--color-on-surface); position:relative; }
  .q-doc-thumb img { width:100%; height:100%; object-fit:cover; display:block; opacity:0; transition:opacity 0.2s; position:relative; z-index:1; }
  .q-thumb-skeleton { position:absolute; inset:0; background:var(--color-surface-dim); animation:q-pulse 1.2s ease-in-out infinite; z-index:0; }
  @keyframes q-pulse { 0%,100% { opacity:0.4; } 50% { opacity:1; } }

  .q-doc-meta { flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; }
  .q-doc-top { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
  .q-doc-filename { font-family:'Space Grotesk',monospace; font-weight:700; font-size:0.75rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .q-doc-title { font-size:0.7rem; color:var(--color-on-surface); font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .q-doc-products { font-size:0.65rem; color:var(--color-on-surface-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .q-doc-more { font-weight:700; color:var(--color-primary); margin-left:4px; }
  .q-doc-company { font-size:0.65rem; color:var(--color-on-surface-dim); text-transform:uppercase; letter-spacing:0.04em; font-weight:700; }
  .q-doc-contact { font-size:0.6rem; color:var(--color-on-surface-dim); font-family:'Space Grotesk',monospace; }

  .q-doc-sep { border-bottom:1px dashed var(--color-on-surface); opacity:0.2; margin:0; }

  /* Terminal -- compact, not fullscreen */
  .q-terminal { margin-top:16px; border:2px solid var(--color-on-surface); }
  .q-terminal-head { display:flex; justify-content:space-between; align-items:center; padding:6px 12px; background:var(--color-on-surface); color:var(--color-surface); }
  .q-terminal-title { font-size:0.65rem; font-weight:900; letter-spacing:0.08em; font-family:'Space Grotesk',monospace; }
  .q-terminal-clear { background:none; border:none; color:rgba(255,255,255,0.5); font-family:inherit; font-size:0.6rem; cursor:pointer; text-transform:uppercase; min-height:20px; }
  .q-terminal-clear:hover { color:#fff; }
  .q-terminal-body { background:#1a1a1a; color:#00fc40; font-family:'Space Grotesk',monospace; font-size:0.7rem; line-height:1.6; padding:8px 12px; max-height:140px; overflow-y:auto; }
  .q-terminal-line { white-space:pre-wrap; }
  .q-blink { animation:qblink 1s step-end infinite; }
  @keyframes qblink { 50% { opacity:0; } }

  /* Empty */
  .q-empty { display:flex; flex-direction:column; align-items:center; gap:12px; padding:48px 16px; text-align:center; color:var(--color-on-surface-dim); }

  /* Responsive: tablet */
  @media (max-width:900px) {
    .q-doc-thumb { width:50px; height:50px; }
    .q-doc-title { max-width:260px; }
    .q-doc-products { max-width:260px; }
  }

  /* Responsive: mobile */
  @media (max-width:640px) {
    .q-row-main { flex-direction:column; align-items:stretch; gap:8px; }
    .q-row-right { flex-wrap:wrap; }
    .q-tags { flex-wrap:wrap; }

    .q-doc-row { flex-direction:column; gap:6px; }
    .q-doc-thumb { width:40px; height:40px; }
    .q-doc-title { max-width:100%; }
    .q-doc-products { max-width:100%; white-space:normal; }
  }
</style>
