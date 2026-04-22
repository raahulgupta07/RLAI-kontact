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

  onMount(async () => {
    try {
      const [statsRes, configRes] = await Promise.all([
        fetch(`${API}/api/stats`),
        fetch(`${API}/api/config`)
      ]);
      stats = await statsRes.json();
      modelConfig = await configRes.json();
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
    font-family: 'Courier New', monospace;
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
</style>
