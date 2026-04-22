<script>
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  const API = '';

  let stats = $state(null);
  let modelConfig = $state(null);
  let searchQuery = $state('');
  let searchResults = $state(null);
  let searching = $state(false);
  let indexing = $state(false);
  let indexResult = $state(null);

  // Table data
  let products = $state([]);
  let contacts = $state([]);
  let companies = $state([]);
  let allDocs = $state([]);
  let documents = $state([]);
  let documentSearch = $state('');
  let productSearch = $state('');
  let contactSearch = $state('');
  let specsSearch = $state('');

  const MAX_PRODUCT_ROWS = 50;

  function fmtDate(d) {
    if (!d) return '';
    try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
  }

  let filteredDocuments = $derived.by(() => {
    if (!documentSearch.trim()) return documents;
    const q = documentSearch.toLowerCase();
    return documents.filter(d =>
      (d.folder || '').toLowerCase().includes(q) ||
      (d.source_file || '').toLowerCase().includes(q) ||
      (d.image_type || '').toLowerCase().includes(q) ||
      (d.company || '').toLowerCase().includes(q) ||
      (d.uuid || '').toLowerCase().includes(q)
    );
  });

  let filteredProducts = $derived.by(() => {
    if (!productSearch.trim()) return products;
    const q = productSearch.toLowerCase();
    return products.filter(p =>
      (p.company || '').toLowerCase().includes(q) ||
      (p.name || '').toLowerCase().includes(q) ||
      (p.model || '').toLowerCase().includes(q) ||
      (p.specs || '').toLowerCase().includes(q) ||
      (p.category || '').toLowerCase().includes(q) ||
      (p.price || '').toLowerCase().includes(q)
    );
  });

  let categoryBreakdown = $derived.by(() => {
    const map = new Map();
    for (const p of products) {
      const cat = p.category || 'Uncategorized';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat).push(p.name || 'Unnamed');
    }
    return Array.from(map.entries())
      .map(([category, names]) => ({
        category,
        count: names.length,
        examples: names.slice(0, 3).join(', ')
      }))
      .sort((a, b) => b.count - a.count);
  });

  let filteredContacts = $derived.by(() => {
    if (!contactSearch.trim()) return contacts;
    const q = contactSearch.toLowerCase();
    return contacts.filter(c =>
      (c.company || '').toLowerCase().includes(q) ||
      (c.person || c.name || '').toLowerCase().includes(q) ||
      (c.phone || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q)
    );
  });

  let filteredSpecs = $derived.by(() => {
    const base = products.filter(p => p.specs);
    if (!specsSearch.trim()) return base.slice(0, 30);
    const q = specsSearch.toLowerCase();
    return base.filter(p =>
      (p.name || '').toLowerCase().includes(q) ||
      (p.model || '').toLowerCase().includes(q) ||
      (p.specs || '').toLowerCase().includes(q) ||
      (p.company || '').toLowerCase().includes(q)
    ).slice(0, 30);
  });

  let productsWithSpecs = $derived.by(() => {
    return products.filter(p => p.specs && p.specs.trim()).slice(0, 30);
  });

  onMount(async () => {
    try {
      const [statsRes, configRes, dataRes, contactsRes, dashRes, docsMetaRes, productsRes] = await Promise.all([
        fetch(`${API}/api/stats`),
        fetch(`${API}/api/config`),
        fetch(`${API}/api/data`),
        fetch(`${API}/api/contacts`),
        fetch(`${API}/api/dashboard`),
        fetch(`${API}/api/documents/metadata`),
        fetch(`${API}/api/products`)
      ]);
      stats = await statsRes.json();
      modelConfig = await configRes.json();

      // Build allDocs from data endpoint
      try {
        const dataJson = await dataRes.json();
        allDocs = Array.isArray(dataJson) ? dataJson : (dataJson.documents || dataJson.data || []);
      } catch (e) {
        console.error('Failed to parse data:', e);
      }

      // Products from normalized table (includes uuid + created_at)
      try {
        const prodsJson = await productsRes.json();
        products = (Array.isArray(prodsJson) ? prodsJson : []).map(p => ({
          uuid: p.uuid || '',
          company: p.company || '',
          name: p.name || p.product_name || '',
          model: p.model || '',
          specs: p.specs || '',
          category: p.category || '',
          price: p.price || '',
          folder: p.folder || '',
          created_at: p.created_at || ''
        }));
      } catch (e) {
        console.error('Failed to load products:', e);
      }

      // Contacts
      try {
        const contactsJson = await contactsRes.json();
        contacts = Array.isArray(contactsJson) ? contactsJson : (contactsJson.contacts || contactsJson.data || []);
      } catch (e) {
        console.error('Failed to load contacts:', e);
      }

      // Companies
      try {
        const dashJson = await dashRes.json();
        companies = dashJson.companies_with_counts || [];
      } catch (e) {
        console.error('Failed to load companies:', e);
      }

      // Documents with metadata
      try {
        const docsMetaJson = await docsMetaRes.json();
        documents = Array.isArray(docsMetaJson) ? docsMetaJson : [];
      } catch (e) {
        console.error('Failed to load documents metadata:', e);
      }
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  });

  async function doSearch() {
    if (!searchQuery.trim()) return;
    searching = true;
    searchResults = null;
    try {
      const [textRes, semRes] = await Promise.all([
        fetch(`${API}/api/search?q=${encodeURIComponent(searchQuery)}`),
        fetch(`${API}/api/search/semantic?q=${encodeURIComponent(searchQuery)}`)
      ]);
      const textData = await textRes.json();
      const semData = await semRes.json();
      searchResults = { text: textData, semantic: semData };
    } catch (e) {
      searchResults = { error: String(e) };
    } finally {
      searching = false;
    }
  }

  async function doReindex() {
    indexing = true;
    indexResult = null;
    try {
      const res = await fetch(`${API}/api/index`, { method: 'POST' });
      indexResult = await res.json();
    } catch (e) {
      indexResult = { error: String(e) };
    } finally {
      indexing = false;
    }
  }
</script>

<div class="page">
  <div class="dark-title-bar">
    <h1>MORE</h1>
    <span class="subtitle">settings + tools</span>
  </div>

  <div class="cards">

    <!-- DATA BROWSER -->
    <button class="card ink-border stamp-shadow" onclick={() => goto('/data')}>
      <div class="card-icon">&#128450;</div>
      <div class="card-body">
        <h2>DATA BROWSER</h2>
        <p>Browse all extracted documents as cards</p>
      </div>
      <div class="card-arrow">&#8594;</div>
    </button>

    <!-- SEARCH -->
    <div class="card ink-border stamp-shadow">
      <div class="card-icon">&#128269;</div>
      <div class="card-body">
        <h2>SEARCH</h2>
        <div class="search-row">
          <input
            type="text"
            class="search-input ink-border"
            placeholder="Search documents..."
            bind:value={searchQuery}
            onkeydown={(e) => e.key === 'Enter' && doSearch()}
          />
          <button class="send-btn" onclick={doSearch} disabled={searching}>
            {searching ? '...' : 'GO'}
          </button>
        </div>
        {#if searchResults?.error}
          <p class="error">{searchResults.error}</p>
        {/if}
        {#if searchResults && !searchResults.error}
          <div class="results">
            {#if searchResults.text?.length}
              <div class="tag-label tag-blue">TEXT MATCHES ({searchResults.text.length})</div>
              {#each searchResults.text.slice(0, 5) as item}
                <div class="result-item">
                  <strong>{item.title || item.source_file || 'Untitled'}</strong>
                  {#if item.company}<span class="tag-label tag-gray">{item.company}</span>{/if}
                </div>
              {/each}
            {/if}
            {#if searchResults.semantic?.length}
              <div class="tag-label tag-purple" style="margin-top:0.5rem">SEMANTIC ({searchResults.semantic.length})</div>
              {#each searchResults.semantic.slice(0, 5) as item}
                <div class="result-item">
                  <strong>{item.title || item.source_file || item.text?.slice(0, 60) || 'Match'}</strong>
                  {#if item.score}<span class="score">{(item.score * 100).toFixed(0)}%</span>{/if}
                </div>
              {/each}
            {/if}
            {#if !searchResults.text?.length && !searchResults.semantic?.length}
              <p class="muted">No results found.</p>
            {/if}
          </div>
        {/if}
      </div>
    </div>

    <!-- EXPORT JSON -->
    <button class="card ink-border stamp-shadow" onclick={() => window.open(`${API}/api/export/json`)}>
      <div class="card-icon">&#128196;</div>
      <div class="card-body">
        <h2>EXPORT JSON</h2>
        <p>Download all extractions as JSON</p>
      </div>
      <div class="card-arrow">&#8595;</div>
    </button>

    <!-- EXPORT CSV -->
    <button class="card ink-border stamp-shadow" onclick={() => window.open(`${API}/api/export/csv`)}>
      <div class="card-icon">&#128202;</div>
      <div class="card-body">
        <h2>EXPORT CSV</h2>
        <p>Download flat table as CSV</p>
      </div>
      <div class="card-arrow">&#8595;</div>
    </button>

    <!-- RE-INDEX -->
    <div class="card ink-border stamp-shadow">
      <div class="card-icon">&#128260;</div>
      <div class="card-body">
        <h2>RE-INDEX</h2>
        <p>Rebuild database + vector index from JSON files</p>
        <button class="send-btn" onclick={doReindex} disabled={indexing}>
          {indexing ? 'INDEXING...' : 'RUN RE-INDEX'}
        </button>
        {#if indexResult}
          <div class="index-result" class:error={indexResult.error}>
            {#if indexResult.error}
              Error: {indexResult.error}
            {:else}
              DB: {indexResult.db_records} records | Vectors: {indexResult.vector_records} records
            {/if}
          </div>
        {/if}
      </div>
    </div>

    <!-- MODELS -->
    <div class="card ink-border stamp-shadow stats-card">
      <div class="card-icon">&#129302;</div>
      <div class="card-body">
        <h2>MODELS</h2>
        {#if modelConfig}
          <div class="stat-row">
            <span class="stat-label">Vision / Chat LLM</span>
            <span class="stat-value"><span class="tag-label tag-green">{modelConfig.vision_model}</span></span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Embeddings</span>
            <span class="stat-value"><span class="tag-label tag-blue">{modelConfig.embedding_model}</span></span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Provider</span>
            <span class="stat-value"><span class="tag-label tag-orange">{modelConfig.provider}</span></span>
          </div>
          <p style="font-size:0.7rem; color:#888; margin-top:0.5rem;">
            Classifier + Extractor + Chat all use the vision model.<br/>
            Embeddings power vector search via OpenRouter.
          </p>
        {:else}
          <p class="muted">Loading...</p>
        {/if}
      </div>
    </div>

    <!-- PRODUCTS TABLE -->
    <div class="card ink-border stamp-shadow stats-card table-card">
      <div class="card-body" style="width:100%">
        <div class="table-header-row">
          <h2>&#128230; PRODUCTS TABLE</h2>
          <button class="send-btn" onclick={() => window.open(`${API}/api/export/xlsx`)}>EXPORT XLSX</button>
        </div>
        <div class="table-toolbar">
          <input
            type="text"
            class="search-input ink-border table-search"
            placeholder="Filter products..."
            bind:value={productSearch}
          />
          <span class="table-count">
            Showing {Math.min(MAX_PRODUCT_ROWS, filteredProducts.length)} of {filteredProducts.length}
          </span>
        </div>
        {#if products.length === 0}
          <p class="muted">Loading products...</p>
        {:else}
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>UUID</th>
                  <th>COMPANY</th>
                  <th>PRODUCT</th>
                  <th>MODEL</th>
                  <th>SPECS</th>
                  <th>CATEGORY</th>
                  <th>PRICE</th>
                  <th>CREATED</th>
                </tr>
              </thead>
              <tbody>
                {#each filteredProducts.slice(0, MAX_PRODUCT_ROWS) as p, i}
                  <tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                    <td class="uuid-cell">{(p.uuid || '').slice(0, 8)}</td>
                    <td>{p.company}</td>
                    <td>{p.name}</td>
                    <td>{p.model}</td>
                    <td class="specs-cell">{p.specs}</td>
                    <td>{p.category}</td>
                    <td>{p.price}</td>
                    <td class="date-cell">{fmtDate(p.created_at)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    <!-- CONTACTS TABLE -->
    <div class="card ink-border stamp-shadow stats-card table-card">
      <div class="card-body" style="width:100%">
        <h2>&#128222; CONTACTS TABLE</h2>
        <input type="text" class="search-input ink-border table-search" placeholder="Filter contacts..." bind:value={contactSearch} />
        {#if contacts.length === 0}
          <p class="muted">Loading contacts...</p>
        {:else}
          <div class="table-scroll">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th>UUID</th>
                  <th>COMPANY</th>
                  <th>PERSON</th>
                  <th>PHONE</th>
                  <th>EMAIL</th>
                  <th>WEBSITE</th>
                </tr>
              </thead>
              <tbody>
                {#each filteredContacts as c, i}
                  <tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                    <td class="uuid-cell">{(c.uuid || '').slice(0, 8)}</td>
                    <td>{c.company || ''}</td>
                    <td>{c.person || c.name || c.contact_name || ''}</td>
                    <td>{c.phone || c.telephone || ''}</td>
                    <td>{c.email || ''}</td>
                    <td>{c.website || c.url || ''}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    <!-- COMPANIES TABLE -->
    <div class="card ink-border stamp-shadow stats-card table-card">
      <div class="card-body" style="width:100%">
        <h2>&#127970; COMPANIES TABLE</h2>
        {#if companies.length === 0}
          <p class="muted">Loading companies...</p>
        {:else}
          <div class="table-scroll">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th>COMPANY</th>
                  <th>DOCUMENTS</th>
                  <th>PRODUCTS</th>
                </tr>
              </thead>
              <tbody>
                {#each companies as c, i}
                  <tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                    <td>{c.company || c.name || ''}</td>
                    <td>{c.documents ?? c.doc_count ?? c.document_count ?? ''}</td>
                    <td>{c.products ?? c.product_count ?? ''}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    <!-- DOCUMENTS TABLE -->
    <div class="card ink-border stamp-shadow stats-card table-card">
      <div class="card-body" style="width:100%">
        <h2>&#128195; DOCUMENTS TABLE</h2>
        <div class="table-toolbar">
          <input
            type="text"
            class="search-input ink-border table-search"
            placeholder="Filter documents..."
            bind:value={documentSearch}
          />
          <span class="table-count">{filteredDocuments.length} documents</span>
        </div>
        {#if documents.length === 0}
          <p class="muted">Loading documents...</p>
        {:else}
          <div class="table-scroll">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th>UUID</th>
                  <th>FOLDER</th>
                  <th>FILE</th>
                  <th>TYPE</th>
                  <th>COMPANY</th>
                  <th>DIMENSIONS</th>
                  <th>FILE SIZE</th>
                  <th>GPS</th>
                  <th>DATE TAKEN</th>
                  <th>IMPORTED</th>
                </tr>
              </thead>
              <tbody>
                {#each filteredDocuments as d, i}
                  {@const m = d.metadata || {}}
                  <tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                    <td class="uuid-cell">{(d.uuid || '').slice(0, 8)}</td>
                    <td>{d.folder || ''}</td>
                    <td>{d.source_file || ''}</td>
                    <td>{d.image_type || ''}</td>
                    <td>{d.company || ''}</td>
                    <td>{m.width && m.height ? `${m.width}x${m.height}` : ''}</td>
                    <td>{m.file_size_kb ? `${m.file_size_kb} KB` : ''}</td>
                    <td>{m.gps_lat && m.gps_lng ? `${m.gps_lat}, ${m.gps_lng}` : ''}</td>
                    <td>{m.date_taken || ''}</td>
                    <td class="date-cell">{fmtDate(d.created_at)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    <!-- CATEGORIES BREAKDOWN -->
    <div class="card ink-border stamp-shadow stats-card table-card">
      <div class="card-body" style="width:100%">
        <h2>&#128202; CATEGORIES BREAKDOWN</h2>
        {#if categoryBreakdown.length === 0}
          <p class="muted">Loading categories...</p>
        {:else}
          <div class="table-scroll">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th>CATEGORY</th>
                  <th>PRODUCT COUNT</th>
                  <th>EXAMPLE PRODUCTS</th>
                </tr>
              </thead>
              <tbody>
                {#each categoryBreakdown as row, i}
                  <tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                    <td>{row.category}</td>
                    <td>{row.count}</td>
                    <td>{row.examples}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    <!-- PRODUCT SPECS -->
    <div class="card ink-border stamp-shadow stats-card table-card">
      <div class="card-body" style="width:100%">
        <h2>&#128295; PRODUCT SPECS</h2>
        <input type="text" class="search-input ink-border table-search" placeholder="Filter specs..." bind:value={specsSearch} />
        {#if filteredSpecs.length === 0}
          <p class="muted">No products with specs found.</p>
        {:else}
          <div class="table-scroll">
            <table class="data-table compact">
              <thead>
                <tr>
                  <th>PRODUCT</th>
                  <th>MODEL</th>
                  <th>SPECS</th>
                  <th>CATEGORY</th>
                  <th>COMPANY</th>
                </tr>
              </thead>
              <tbody>
                {#each filteredSpecs as p, i}
                  <tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                    <td>{p.name}</td>
                    <td>{p.model}</td>
                    <td class="specs-cell-wide">{p.specs}</td>
                    <td>{p.category}</td>
                    <td>{p.company}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    <!-- IMAGE GALLERY -->
    <div class="card ink-border stamp-shadow stats-card table-card">
      <div class="card-body" style="width:100%">
        <h2>&#128247; IMAGE GALLERY</h2>
        {#if allDocs.length === 0}
          <p class="muted">Loading images...</p>
        {:else}
          <div class="gallery-grid">
            {#each allDocs as doc}
              {#if doc.source_file && doc.folder}
                <a
                  class="gallery-thumb"
                  href="{API}/api/image/{doc.folder}/{doc.source_file}"
                  target="_blank"
                  rel="noopener"
                  title={doc.source_file}
                >
                  <img
                    src="{API}/api/image/{doc.folder}/{doc.source_file}"
                    alt={doc.source_file}
                    loading="lazy"
                  />
                </a>
              {/if}
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- STATS -->
    <div class="card ink-border stamp-shadow stats-card">
      <div class="card-icon">&#128200;</div>
      <div class="card-body">
        <h2>STATS</h2>
        {#if stats}
          <div class="stat-row">
            <span class="stat-label">Total Documents</span>
            <span class="stat-value">{stats.total_docs ?? stats.total ?? '?'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Folders</span>
            <span class="stat-value">{stats.folders?.length ?? stats.folder_count ?? '?'}</span>
          </div>
          {#if stats.folders?.length}
            <div class="stat-tags">
              {#each stats.folders as folder}
                <span class="tag-label tag-blue">{folder}</span>
              {/each}
            </div>
          {/if}
          {#if stats.companies?.length}
            <div class="stat-row">
              <span class="stat-label">Companies</span>
              <span class="stat-value">{stats.companies.length}</span>
            </div>
            <div class="stat-tags">
              {#each stats.companies as company}
                <span class="tag-label tag-orange">{company}</span>
              {/each}
            </div>
          {/if}
        {:else}
          <p class="muted">Loading stats...</p>
        {/if}
      </div>
    </div>

  </div>
</div>

<style>
  .page {
    max-width: 100%;
    margin: 0 auto;
    padding: 0 1rem 6rem;
    font-family: 'Space Grotesk', monospace, sans-serif;
  }

  .dark-title-bar {
    background: #1a1a1a;
    color: #f5f0e8;
    padding: 1.25rem 1rem;
    margin: 0 -1rem 1.5rem;
    border-bottom: 3px solid #000;
  }
  .dark-title-bar h1 {
    margin: 0;
    font-size: 1.5rem;
    letter-spacing: 0.15em;
  }
  .dark-title-bar .subtitle {
    font-size: 0.75rem;
    opacity: 0.6;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .cards {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .card {
    background: #fffef8;
    padding: 1rem;
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    width: 100%;
    text-align: left;
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
    transition: transform 0.1s;
  }
  .card:active {
    transform: scale(0.98);
  }

  .ink-border {
    border: 2px solid #1a1a1a;
    border-radius: 2px;
  }

  .stamp-shadow {
    box-shadow: 3px 3px 0 #1a1a1a;
  }

  .card-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
    width: 2rem;
    text-align: center;
  }

  .card-body {
    flex: 1;
    min-width: 0;
  }
  .card-body h2 {
    margin: 0 0 0.25rem;
    font-size: 1rem;
    letter-spacing: 0.08em;
  }
  .card-body p {
    margin: 0;
    font-size: 0.8rem;
    color: #555;
  }

  .card-arrow {
    font-size: 1.25rem;
    align-self: center;
    flex-shrink: 0;
  }

  .search-row {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .search-input {
    flex: 1;
    padding: 0.6rem 0.75rem;
    font-family: inherit;
    font-size: 0.9rem;
    background: #fff;
    outline: none;
  }

  .send-btn {
    background: #1a1a1a;
    color: #f5f0e8;
    border: 2px solid #1a1a1a;
    padding: 0.6rem 1.25rem;
    font-family: inherit;
    font-weight: bold;
    font-size: 0.85rem;
    letter-spacing: 0.08em;
    cursor: pointer;
    white-space: nowrap;
  }
  .send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .send-btn:active:not(:disabled) {
    background: #333;
  }

  .results {
    margin-top: 0.75rem;
  }

  .result-item {
    padding: 0.4rem 0;
    border-bottom: 1px dashed #ccc;
    font-size: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .score {
    font-size: 0.7rem;
    background: #eee;
    padding: 0.1rem 0.4rem;
    border-radius: 2px;
  }

  .tag-label {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: bold;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.15rem 0.5rem;
    border: 1px solid currentColor;
    margin: 0.15rem 0.15rem 0.15rem 0;
  }
  .tag-blue { color: #fff; background: #2563eb; border-color: #2563eb; }
  .tag-purple { color: #fff; background: #7c3aed; border-color: #7c3aed; }
  .tag-orange { color: #fff; background: #d97706; border-color: #d97706; }
  .tag-gray { color: #fff; background: #6b7280; border-color: #6b7280; }
  .tag-green { color: #fff; background: #16a34a; border-color: #16a34a; }

  .index-result {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: #f0fdf4;
    border: 1px solid #86efac;
    font-size: 0.8rem;
  }
  .index-result.error {
    background: #fef2f2;
    border-color: #fca5a5;
    color: #b91c1c;
  }

  .stats-card {
    cursor: default;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    padding: 0.35rem 0;
    border-bottom: 1px dashed #ddd;
    font-size: 0.85rem;
  }
  .stat-label { color: #555; }
  .stat-value { font-weight: bold; }

  .stat-tags {
    padding: 0.4rem 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .muted {
    color: #999;
    font-size: 0.8rem;
    font-style: italic;
  }

  .error {
    color: #b91c1c;
    font-size: 0.8rem;
  }

  /* --- Data Tables --- */
  .table-card {
    flex-direction: column;
  }

  .table-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .table-toolbar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.5rem 0;
    flex-wrap: wrap;
  }

  .table-search {
    flex: 1;
    min-width: 140px;
    padding: 0.4rem 0.6rem;
    font-size: 0.75rem;
  }

  .table-count {
    font-size: 0.65rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
  }

  .table-scroll {
    overflow-x: auto;
    overflow-y: auto;
    max-height: 400px;
    -webkit-overflow-scrolling: touch;
    margin-top: 0.25rem;
    border: 2px solid #1a1a1a;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Space Grotesk', monospace, sans-serif;
    font-size: 12px;
    min-width: 500px;
  }

  .data-table.compact {
    font-size: 11px;
  }

  .data-table thead tr {
    background: var(--color-on-surface);
    color: var(--color-surface);
  }

  .data-table th {
    padding: 6px 10px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    text-align: left;
    border: 1px solid var(--color-on-surface);
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--color-on-surface);
  }

  .data-table td {
    padding: 5px 10px;
    border: 1px solid var(--color-on-surface);
    vertical-align: top;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--color-on-surface);
  }

  .data-table .specs-cell {
    max-width: 250px;
  }

  .row-even {
    background: var(--color-surface-bright);
  }

  .row-odd {
    background: var(--color-surface-dim);
  }

  .data-table tbody tr:hover {
    background: var(--color-surface-dim);
    opacity: 0.9;
  }

  .data-table .uuid-cell {
    font-family: 'Space Grotesk', monospace;
    font-size: 10px;
    letter-spacing: 0.04em;
    color: #6b7280;
    max-width: 70px;
  }

  .data-table .date-cell {
    font-size: 10px;
    white-space: nowrap;
    color: #6b7280;
  }

  .data-table .specs-cell-wide {
    max-width: 300px;
    word-wrap: break-word;
    white-space: normal;
    overflow-wrap: break-word;
  }

  /* --- Image Gallery --- */
  .gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    gap: 6px;
    margin-top: 0.5rem;
  }

  .gallery-thumb {
    display: block;
    width: 80px;
    height: 80px;
    overflow: hidden;
    border: 2px solid #1a1a1a;
    background: #f5f0e8;
  }

  .gallery-thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .gallery-thumb:hover {
    border-color: #2563eb;
    box-shadow: 2px 2px 0 #2563eb;
  }
</style>
