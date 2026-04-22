<script>
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  const API = '';

  let docs = $state([]);
  let filtered = $state([]);
  let expandedId = $state(null);
  let loading = $state(true);

  let folderFilter = $state('All');
  let typeFilter = $state('All');
  let sortOption = $state('newest');
  let folders = $state([]);
  let imageTypes = $state([]);
  let copyFeedback = $state({});

  function tryParse(val) {
    if (!val) return val;
    if (typeof val === 'string') { try { return JSON.parse(val); } catch { return val; } }
    return val;
  }

  function formatTimestamp(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' +
           d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  }

  function applySorting(arr) {
    const sorted = [...arr];
    switch (sortOption) {
      case 'newest':
        sorted.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
        break;
      case 'oldest':
        sorted.sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0));
        break;
      case 'type':
        sorted.sort((a, b) => (a.image_type || '').localeCompare(b.image_type || ''));
        break;
      case 'company':
        sorted.sort((a, b) => (a.company || '').localeCompare(b.company || ''));
        break;
      case 'folder':
        sorted.sort((a, b) => (a.folder || '').localeCompare(b.folder || ''));
        break;
    }
    return sorted;
  }

  onMount(async () => {
    try {
      const res = await fetch(`${API}/api/data`);
      const raw = await res.json();
      docs = (Array.isArray(raw) ? raw : []).map(d => ({
        ...d,
        products: tryParse(d.products) || [],
        contact: tryParse(d.contact) || {},
        key_info: tryParse(d.key_info) || []
      }));

      const folderSet = new Set();
      const typeSet = new Set();
      for (const d of docs) {
        if (d.folder) folderSet.add(d.folder);
        if (d.image_type) typeSet.add(d.image_type);
      }
      folders = [...folderSet].sort();
      imageTypes = [...typeSet].sort();

      applyFilters();
    } catch (e) {
      console.error('Failed to load data:', e);
    } finally {
      loading = false;
    }
  });

  function applyFilters() {
    let result = docs.filter(d => {
      if (folderFilter !== 'All' && d.folder !== folderFilter) return false;
      if (typeFilter !== 'All' && d.image_type !== typeFilter) return false;
      return true;
    });
    filtered = applySorting(result);
  }

  function onFolderChange(e) {
    folderFilter = e.target.value;
    applyFilters();
  }

  function onTypeChange(e) {
    typeFilter = e.target.value;
    applyFilters();
  }

  function onSortChange(e) {
    sortOption = e.target.value;
    applyFilters();
  }

  function toggleExpand(id) {
    expandedId = expandedId === id ? null : id;
  }

  function typeColor(type) {
    const map = {
      product_page: 'tag-green',
      tech_diagram: 'tag-blue',
      cover: 'tag-orange',
      contact_page: 'tag-purple',
      company_profile: 'tag-teal',
      other: 'tag-gray',
      price_list: 'tag-red',
      section_divider: 'tag-slate'
    };
    return map[type] || 'tag-gray';
  }

  let showRawText = $state({});
  let showJson = $state({});

  function toggleRaw(id) {
    showRawText = { ...showRawText, [id]: !showRawText[id] };
  }

  function toggleJson(id) {
    showJson = { ...showJson, [id]: !showJson[id] };
  }

  async function copyDocText(doc, docId) {
    const lines = [];
    lines.push(`Title: ${doc.title || doc.source_file || 'Untitled'}`);
    if (doc.company) lines.push(`Company: ${doc.company}`);
    lines.push(`Type: ${doc.image_type || 'unknown'}`);
    lines.push(`Source: ${doc.source_file} / ${doc.folder}`);
    if (doc.created_at) lines.push(`Created: ${formatTimestamp(doc.created_at)}`);
    if (doc.products?.length) {
      lines.push('\nProducts:');
      for (const p of doc.products) {
        lines.push(`  - ${p.name || 'Unnamed'}${p.model ? ' (' + p.model + ')' : ''}${p.category ? ' [' + p.category + ']' : ''}`);
      }
    }
    if (doc.contact && Object.values(doc.contact).some(v => v)) {
      lines.push('\nContact:');
      for (const [k, v] of Object.entries(doc.contact)) {
        if (v) lines.push(`  ${k}: ${v}`);
      }
    }
    if (doc.key_info?.length) {
      lines.push('\nKey Info:');
      for (const info of doc.key_info) lines.push(`  - ${info}`);
    }
    if (doc.raw_text) lines.push(`\nRaw Text:\n${doc.raw_text}`);
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      copyFeedback = { ...copyFeedback, [docId]: true };
      setTimeout(() => { copyFeedback = { ...copyFeedback, [docId]: false }; }, 1500);
    } catch (e) {
      console.error('Copy failed', e);
    }
  }

  function saveJson(doc) {
    const json = JSON.stringify(doc, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(doc.source_file || 'document').replace(/\.[^.]+$/, '')}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
</script>

<div class="page">
  <!-- HEADER ROW -->
  <div class="header-row">
    <div class="header-left">
      <h1>DATA BROWSER</h1>
      <span class="header-count">{filtered.length} of {docs.length} documents</span>
    </div>
    <div class="header-right">
      <select class="sort-select ink-border" onchange={onSortChange} value={sortOption}>
        <option value="newest">Newest First</option>
        <option value="oldest">Oldest First</option>
        <option value="type">By Type</option>
        <option value="company">By Company</option>
        <option value="folder">By Folder</option>
      </select>
    </div>
  </div>

  <!-- FILTER BAR -->
  <div class="filter-bar ink-border">
    <div class="filter-group">
      <label>Folder</label>
      <select class="filter-select ink-border" onchange={onFolderChange} value={folderFilter}>
        <option value="All">All Folders</option>
        {#each folders as f}
          <option value={f}>{f}</option>
        {/each}
      </select>
    </div>
    <div class="filter-group">
      <label>Type</label>
      <select class="filter-select ink-border" onchange={onTypeChange} value={typeFilter}>
        <option value="All">All Types</option>
        {#each imageTypes as t}
          <option value={t}>{t}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if loading}
    <div class="loading">Loading documents...</div>
  {:else if filtered.length === 0}
    <div class="loading">No documents found.</div>
  {:else}
    <div class="card-list">
      {#each filtered as doc, i}
        {@const docId = doc.id ?? i}
        <div class="card ink-border stamp-shadow" class:expanded={expandedId === docId}>
          <!-- CARD HEADER -->
          <button class="card-header" onclick={() => toggleExpand(docId)}>
            <div class="card-header-row">
              <img src={`/api/image/${doc.folder}/${doc.source_file}`} alt={doc.source_file} class="card-thumb" loading="lazy" onerror={(e) => e.target.style.display='none'} />
              <div class="card-header-info">
                <div class="card-top-row">
                  <span class="tag-label {typeColor(doc.image_type)}">{doc.image_type || 'unknown'}</span>
                  <span class="card-index">#{i + 1}</span>
                </div>
                <h3 class="card-title">{doc.title || doc.source_file || 'Untitled'}</h3>
                {#if doc.company}<p class="card-company">{doc.company}</p>{/if}
                <p class="card-source">{doc.source_file} · {doc.folder}</p>
                <div class="card-meta-row">
                  {#if doc.img_width && doc.img_height}<span class="meta-tag">{doc.img_width}x{doc.img_height}</span>{/if}
                  {#if doc.file_size_kb}<span class="meta-tag">{doc.file_size_kb} KB</span>{/if}
                  {#if doc.uuid}<span class="meta-tag uuid">{doc.uuid.slice(0, 8)}</span>{/if}
                  {#if doc.gps_lat && doc.gps_lng}<span class="meta-tag gps">{doc.gps_lat}, {doc.gps_lng}</span>{/if}
                  {#if doc.date_taken}<span class="meta-tag">{doc.date_taken}</span>{/if}
                  {#if doc.camera_make}<span class="meta-tag">{doc.camera_make} {doc.camera_model || ''}</span>{/if}
                </div>
                {#if doc.created_at}
                  <p class="card-timestamp">{formatTimestamp(doc.created_at)}</p>
                {/if}
              </div>
            </div>
          </button>

          <!-- EXPANDED DETAILS -->
          {#if expandedId === docId}
            <div class="card-details">

              <!-- Action buttons -->
              <div class="action-bar">
                <button class="action-btn" onclick={() => copyDocText(doc, docId)}>
                  {copyFeedback[docId] ? 'COPIED!' : 'COPY'}
                </button>
                <button class="action-btn" onclick={() => saveJson(doc)}>
                  SAVE JSON
                </button>
              </div>

              <!-- Metadata -->
              <div class="detail-section">
                <h4>File Info</h4>
                <div class="meta-grid">
                  {#if doc.uuid}<div class="meta-item"><span class="meta-label">UUID</span><span class="meta-value">{doc.uuid}</span></div>{/if}
                  {#if doc.img_width}<div class="meta-item"><span class="meta-label">Dimensions</span><span class="meta-value">{doc.img_width} x {doc.img_height} px</span></div>{/if}
                  {#if doc.file_size_kb}<div class="meta-item"><span class="meta-label">File Size</span><span class="meta-value">{doc.file_size_kb} KB</span></div>{/if}
                  {#if doc.gps_lat && doc.gps_lng}<div class="meta-item"><span class="meta-label">GPS Location</span><span class="meta-value">{doc.gps_lat}, {doc.gps_lng}</span></div>{/if}
                  {#if doc.date_taken}<div class="meta-item"><span class="meta-label">Date Taken</span><span class="meta-value">{doc.date_taken}</span></div>{/if}
                  {#if doc.camera_make}<div class="meta-item"><span class="meta-label">Camera</span><span class="meta-value">{doc.camera_make} {doc.camera_model || ''}</span></div>{/if}
                  {#if doc.created_at}<div class="meta-item"><span class="meta-label">Imported</span><span class="meta-value">{formatTimestamp(doc.created_at)}</span></div>{/if}
                  <div class="meta-item"><span class="meta-label">Folder</span><span class="meta-value">{doc.folder}</span></div>
                  <div class="meta-item"><span class="meta-label">Type</span><span class="meta-value">{doc.image_type}</span></div>
                </div>
              </div>

              <!-- Products -->
              {#if doc.products?.length}
                <div class="detail-section">
                  <h4>Products</h4>
                  {#each doc.products as prod}
                    <div class="product-item ink-border">
                      <strong>{prod.name || 'Unnamed Product'}</strong>
                      {#if prod.model}<div class="prod-field">Model: {prod.model}</div>{/if}
                      {#if prod.category}<div class="prod-field">Category: {prod.category}</div>{/if}
                      {#if prod.specs}
                        <div class="prod-field">Specs: {typeof prod.specs === 'string' ? prod.specs : JSON.stringify(prod.specs)}</div>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}

              <!-- Contact Info -->
              {#if doc.contact && (doc.contact.phone || doc.contact.email || doc.contact.website || doc.contact.address || doc.contact.person)}
                <div class="detail-section">
                  <h4>Contact Info</h4>
                  {#if doc.contact.person}<div class="contact-item">Person: {doc.contact.person}</div>{/if}
                  {#if doc.contact.phone}<div class="contact-item">Phone: {doc.contact.phone}</div>{/if}
                  {#if doc.contact.email}<div class="contact-item">Email: {doc.contact.email}</div>{/if}
                  {#if doc.contact.website}<div class="contact-item">Website: {doc.contact.website}</div>{/if}
                  {#if doc.contact.address}<div class="contact-item">Address: {doc.contact.address}</div>{/if}
                </div>
              {/if}

              <!-- Key Info -->
              {#if doc.key_info?.length}
                <div class="detail-section">
                  <h4>Key Info</h4>
                  <ul class="key-info-list">
                    {#each doc.key_info as info}
                      <li>{info}</li>
                    {/each}
                  </ul>
                </div>
              {/if}

              <!-- Raw Text (collapsible) -->
              {#if doc.raw_text}
                <div class="detail-section">
                  <button class="collapse-toggle" onclick={() => toggleRaw(docId)}>
                    {showRawText[docId] ? '[-]' : '[+]'} Raw Text
                  </button>
                  {#if showRawText[docId]}
                    <div class="cli-terminal">
                      <pre>{doc.raw_text}</pre>
                    </div>
                  {/if}
                </div>
              {/if}

              <!-- Full JSON (collapsible) -->
              <div class="detail-section">
                <button class="collapse-toggle" onclick={() => toggleJson(docId)}>
                  {showJson[docId] ? '[-]' : '[+]'} Full JSON
                </button>
                {#if showJson[docId]}
                  <div class="cli-terminal">
                    <pre>{JSON.stringify(doc, null, 2)}</pre>
                  </div>
                {/if}
              </div>

            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    max-width: 100%;
    margin: 0 auto;
    padding: 16px 1rem 6rem;
    font-family: 'Courier New', monospace;
  }

  /* Header - matching queue page style */
  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }
  .header-left {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .header-left h1 {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 900;
    letter-spacing: 0.08em;
  }
  .header-count {
    font-size: 0.7rem;
    color: #999;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .header-right {
    display: flex;
    align-items: center;
  }

  .sort-select {
    padding: 6px 10px;
    font-family: inherit;
    font-size: 0.75rem;
    font-weight: 700;
    background: #fff;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .filter-bar {
    display: flex;
    gap: 0.75rem;
    padding: 0.75rem;
    background: #f9f8f2;
    margin-bottom: 1rem;
  }

  .filter-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .filter-group label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #888;
    font-weight: bold;
  }

  .filter-select {
    padding: 0.5rem;
    font-family: inherit;
    font-size: 0.8rem;
    background: #fff;
    cursor: pointer;
  }

  .ink-border {
    border: 2px solid #1a1a1a;
    border-radius: 2px;
  }

  .stamp-shadow {
    box-shadow: 3px 3px 0 #1a1a1a;
  }

  .loading {
    text-align: center;
    padding: 3rem 1rem;
    color: #999;
    font-style: italic;
  }

  .card-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .card {
    background: #fffef8;
    overflow: hidden;
    transition: box-shadow 0.15s;
  }
  .card.expanded {
    box-shadow: 4px 4px 0 #1a1a1a, 0 0 0 1px #1a1a1a;
  }

  .card-header {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    padding: 1rem;
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
  }
  .card-header:active {
    background: #f5f4ee;
  }
  .card-header-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  .card-thumb {
    width: 60px;
    height: 60px;
    object-fit: cover;
    border: 2px solid #1a1a1a;
    flex-shrink: 0;
  }
  .card-header-info {
    flex: 1;
    min-width: 0;
  }

  .card-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.4rem;
  }

  .card-index {
    font-size: 0.7rem;
    color: #aaa;
  }

  /* Tag labels with solid background colors */
  .tag-label {
    display: inline-block;
    font-size: 0.6rem;
    font-weight: bold;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.15rem 0.5rem;
    border: none;
  }
  .tag-green  { background: #16a34a; color: #fff; }
  .tag-blue   { background: #2563eb; color: #fff; }
  .tag-orange { background: #d97706; color: #fff; }
  .tag-purple { background: #7c3aed; color: #fff; }
  .tag-teal   { background: #0891b2; color: #fff; }
  .tag-gray   { background: #6b7280; color: #fff; }
  .tag-red    { background: #dc2626; color: #fff; }
  .tag-slate  { background: #475569; color: #fff; }

  .card-title {
    margin: 0;
    font-size: 0.95rem;
    line-height: 1.3;
  }

  .card-company {
    margin: 0.2rem 0 0;
    font-size: 0.8rem;
    color: #555;
    font-weight: bold;
  }

  .card-source {
    margin: 0.15rem 0 0;
    font-size: 0.7rem;
    color: #999;
    word-break: break-all;
  }

  .card-timestamp {
    margin: 0.15rem 0 0;
    font-size: 0.65rem;
    color: #aaa;
    letter-spacing: 0.03em;
  }

  .card-details {
    border-top: 2px dashed #ccc;
    padding: 1rem;
  }

  /* Action buttons bar */
  .action-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 1rem;
  }
  .action-btn {
    font-family: inherit;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 6px 14px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    cursor: pointer;
    border: 2px solid #1a1a1a;
    background: #fff;
    color: #1a1a1a;
    min-height: 32px;
  }
  .action-btn:active {
    background: #f0f0e8;
  }

  .detail-section {
    margin-bottom: 1rem;
  }
  .detail-section h4 {
    margin: 0 0 0.4rem;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #333;
    border-bottom: 1px solid #ddd;
    padding-bottom: 0.25rem;
  }

  .product-item {
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    background: #fafaf4;
    font-size: 0.8rem;
  }
  .prod-field {
    font-size: 0.75rem;
    color: #555;
    margin-top: 0.15rem;
  }

  .contact-item {
    font-size: 0.8rem;
    padding: 0.25rem 0;
    color: #444;
    white-space: pre-wrap;
  }

  .key-info-list {
    margin: 0;
    padding-left: 1.25rem;
    font-size: 0.8rem;
    color: #444;
  }
  .key-info-list li {
    margin-bottom: 0.2rem;
  }

  .collapse-toggle {
    background: none;
    border: none;
    font-family: inherit;
    font-size: 0.8rem;
    font-weight: bold;
    color: #555;
    cursor: pointer;
    padding: 0.25rem 0;
    letter-spacing: 0.05em;
  }
  .collapse-toggle:hover {
    color: #000;
  }

  .cli-terminal {
    background: #1a1a1a;
    color: #4ade80;
    padding: 0.75rem;
    margin-top: 0.4rem;
    border-radius: 2px;
    overflow-x: auto;
    max-height: 300px;
    overflow-y: auto;
  }
  .cli-terminal pre {
    margin: 0;
    font-size: 0.7rem;
    line-height: 1.4;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* Metadata tags on card header */
  .card-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }
  .meta-tag {
    font-size: 0.55rem;
    font-weight: 700;
    padding: 1px 6px;
    background: var(--color-surface-dim);
    border: 1px solid var(--color-on-surface);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-family: 'Space Grotesk', monospace;
    color: var(--color-on-surface-dim);
  }
  .meta-tag.uuid { color: #7c3aed; border-color: #7c3aed; }
  .meta-tag.gps { color: #16a34a; border-color: #16a34a; background: #dcfce7; }

  .card-timestamp {
    margin: 3px 0 0;
    font-size: 0.6rem;
    color: #999;
  }

  /* Metadata grid in expanded details */
  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 4px 6px;
    background: var(--color-surface-dim);
    border: 1px solid rgba(0,0,0,0.08);
  }
  .meta-label {
    font-size: 0.55rem;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-on-surface-dim);
  }
  .meta-value {
    font-size: 0.75rem;
    font-family: 'Space Grotesk', monospace;
    word-break: break-all;
  }
  @media (max-width: 640px) {
    .meta-grid { grid-template-columns: 1fr; }
  }
</style>
