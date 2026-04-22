<script>
  import { onMount } from 'svelte';
  import { markdownToHtml } from '$lib/markdown';

  let messages = $state([]);
  let input = $state('');
  let sessionId = $state(null);
  let sessions = $state([]);
  let loading = $state(false);
  let showHistory = $state(false);
  let modelConfig = $state(null);
  let streamingText = $state('');
  let toolSteps = $state([]);
  let abortController = $state(null);
  let expandedImg = $state(null);
  let historyFilter = $state('');
  let isListening = $state(false);

  let chatContainer = $state(null);
  let textareaEl = $state(null);
  let copiedIdx = $state(-1);
  let feedbackState = $state({});

  function getTimestamp() { return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'Z');
    const diff = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  async function copyText(text, idx) {
    try { await navigator.clipboard.writeText(text); copiedIdx = idx; setTimeout(() => { copiedIdx = -1; }, 1500); } catch (err) { console.error('Copy failed:', err); }
  }
  function exportCSV(text) {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'kontact-response.txt'; a.click(); URL.revokeObjectURL(url);
  }
  function exportChatMarkdown() {
    if (messages.length === 0) return;
    const lines = messages.map(msg => {
      if (msg.role === 'user') return `> ${msg.content}`;
      return msg.content;
    });
    const md = lines.join('\n\n---\n\n');
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `kontact-chat-${new Date().toISOString().slice(0,10)}.md`; a.click(); URL.revokeObjectURL(url);
  }
  async function submitFeedback(idx, rating) {
    if (feedbackState[idx]) return;
    const msg = messages[idx];
    // Find the preceding user message
    let question = '';
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === 'user') { question = messages[i].content; break; }
    }
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId || '', question, answer: msg.content, rating })
      });
      feedbackState = { ...feedbackState, [idx]: rating };
    } catch (err) { console.error('Feedback error:', err); }
  }

  function extractSuggestions(answer) {
    const lower = answer.toLowerCase();
    const suggestions = [];
    const map = [
      [['price', 'cost', 'pricing'], 'Compare pricing across vendors'],
      [['security', 'surveillance', 'camera'], 'What security features are offered?'],
      [['product', 'model', 'catalog'], 'List all product specifications'],
      [['company', 'vendor', 'manufacturer'], 'Tell me more about this company'],
      [['contact', 'email', 'phone'], 'Show all contact details'],
      [['spec', 'technical', 'feature'], 'Compare technical specifications'],
    ];
    for (const [kws, sug] of map) { if (kws.some(k => lower.includes(k))) suggestions.push(sug); if (suggestions.length >= 3) break; }
    if (suggestions.length === 0) suggestions.push('Tell me more', 'Compare all vendors');
    return suggestions.slice(0, 3);
  }

  const defaultChips = ['Compare all vendors', 'List all products', 'What security systems are available?'];
  $effect(() => { if (typeof localStorage !== 'undefined') localStorage.setItem('kontact-showHistory', String(showHistory)); });
  $effect(() => { document.body.style.overflow = expandedImg ? 'hidden' : 'auto'; });
  $effect(() => {
    if (chatContainer && (messages.length || streamingText || toolSteps.length))
      requestAnimationFrame(() => { chatContainer.scrollTop = chatContainer.scrollHeight; });
  });
  function autoGrow() { if (!textareaEl) return; textareaEl.style.height = 'auto'; textareaEl.style.height = Math.min(textareaEl.scrollHeight, 80) + 'px'; }

  async function send(text) {
    const question = (text ?? input).trim();
    if (!question || loading) return;
    input = ''; if (textareaEl) textareaEl.style.height = 'auto';
    messages = [...messages, { role: 'user', content: question, timestamp: getTimestamp() }];
    loading = true; streamingText = ''; toolSteps = [];
    abortController = new AbortController();
    let streamTimeout = null;
    let receivedContent = false;
    function resetStreamTimeout() {
      if (streamTimeout) clearTimeout(streamTimeout);
      streamTimeout = setTimeout(() => {
        if (!receivedContent && abortController) {
          abortController.abort();
          messages = [...messages, { role: 'assistant', content: streamingText || 'Request timed out. The server took too long to respond.', sources: [], timestamp: getTimestamp() }];
          streamingText = ''; loading = false; toolSteps = []; abortController = null;
        }
      }, 60000);
    }
    resetStreamTimeout();
    try {
      const res = await fetch('/api/chat/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, session_id: sessionId }), signal: abortController.signal });
      const reader = res.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      while (true) {
        const { value, done } = await reader.read(); if (done) break;
        resetStreamTimeout();
        buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || '';
        let currentEvent = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) { currentEvent = line.slice(7).trim(); }
          else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (currentEvent === 'session') sessionId = data.session_id;
              else if (currentEvent === 'status') { toolSteps = toolSteps.map(s => ({ ...s, done: true })); toolSteps = [...toolSteps, { text: data.step, done: false }]; }
              else if (currentEvent === 'content') { receivedContent = true; if (toolSteps.length && !toolSteps[toolSteps.length - 1].done) toolSteps = toolSteps.map(s => ({ ...s, done: true })); streamingText += data.text; }
              else if (currentEvent === 'done') {
                const rawSources = data.sources ?? [];
                const seen = new Set();
                const uniqueSources = rawSources.filter(s => { const key = `${s.folder}/${s.file}`; if (seen.has(key)) return false; seen.add(key); return true; });
                messages = [...messages, { role: 'assistant', content: streamingText, sources: uniqueSources, timestamp: getTimestamp() }]; streamingText = '';
              }
            } catch (_) {}
          }
        }
      }
    } catch (err) {
      console.error('Chat error:', err);
      if (err.name !== 'AbortError') messages = [...messages, { role: 'assistant', content: streamingText || 'Sorry, something went wrong.', sources: [], timestamp: getTimestamp() }];
      streamingText = '';
    } finally { if (streamTimeout) clearTimeout(streamTimeout); loading = false; toolSteps = []; abortController = null; }
  }

  let filteredSessions = $derived(
    historyFilter.trim()
      ? sessions.filter(s => (s.preview || '').toLowerCase().includes(historyFilter.trim().toLowerCase()))
      : sessions
  );

  function toggleVoice() {
    if (isListening) { isListening = false; return; }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { alert('Speech recognition not supported in this browser.'); return; }
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => { const transcript = event.results[0][0].transcript; input = input ? input + ' ' + transcript : transcript; };
    recognition.onend = () => { isListening = false; };
    recognition.onerror = () => { isListening = false; };
    recognition.start();
    isListening = true;
  }

  function stopStreaming() { if (abortController) abortController.abort(); }
  function handleKeydown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }

  async function loadSession(sid) {
    sessionId = sid;
    const res = await fetch(`/api/chat/history/${sid}`); if (!res.ok) return;
    const history = await res.json();
    messages = history.map(h => ({ role: h.role, content: h.content, sources: [], timestamp: '' }));
  }
  async function newSession() { sessionId = null; messages = []; }
  async function deleteSession(sid) {
    await fetch(`/api/chat/sessions/${sid}`, { method: 'DELETE' });
    sessions = sessions.filter(s => s.session_id !== sid);
    if (sessionId === sid) { sessionId = null; messages = []; }
  }
  async function refreshSessions() { const res = await fetch('/api/chat/sessions'); if (res.ok) sessions = await res.json(); }

  onMount(async () => {
    const saved = localStorage.getItem('kontact-showHistory');
    if (saved === 'true') showHistory = true;
    await refreshSessions();
    try { const res = await fetch('/api/config'); modelConfig = await res.json(); } catch {}
  });
</script>

<svelte:head><title>KONTACT AGENT</title></svelte:head>

<!-- Image lightbox -->
{#if expandedImg}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="lightbox" onclick={() => expandedImg = null} onkeydown={(e) => e.key === 'Escape' && (expandedImg = null)}>
    <img src={expandedImg.src} alt={expandedImg.alt} class="lightbox-img" />
    <div class="lightbox-caption">{expandedImg.alt}</div>
    <button class="lightbox-close" aria-label="Close image" onclick={() => expandedImg = null}>&times;</button>
  </div>
{/if}

<div class="chat-page">
  <header class="chat-header">
    <h1>KONTACT Agent</h1>
    <div style="display:flex;gap:6px;">
      <button class="header-btn mobile-only" class:active={showHistory} onclick={() => { showHistory = !showHistory; if (showHistory) refreshSessions(); }}>History</button>
      <button class="header-btn new" onclick={newSession}>+ New</button>
      {#if messages.length > 0}<button class="header-btn" onclick={exportChatMarkdown}>Export</button>{/if}
    </div>
  </header>


  <div class="chat-body">
    <aside class="history-panel" class:show-mobile={showHistory}>
      <div class="history-title">CHAT HISTORY</div>
      <div class="history-search-wrap">
        <input class="history-search" type="text" bind:value={historyFilter} placeholder="Search sessions..." />
      </div>
      {#each filteredSessions as s}
        <div class="history-item" class:active={sessionId === s.session_id}>
          <button class="history-item-btn" onclick={() => loadSession(s.session_id)}>
            <span class="history-preview">{s.preview || s.session_id}{#if s.preview && s.preview.length >= 50}...{/if}</span>
            <span class="history-meta">{timeAgo(s.last_msg)}</span>
          </button>
          <button class="history-delete" onclick={() => deleteSession(s.session_id)} title="Delete">&times;</button>
        </div>
      {/each}
      {#if filteredSessions.length === 0}<p class="history-empty">{historyFilter.trim() ? 'No matching sessions' : 'No sessions yet'}</p>{/if}
    </aside>

    <div class="messages" bind:this={chatContainer}>
      {#if messages.length === 0 && !loading}
        <div class="empty-state">
          <div class="empty-icon"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:0.3"><rect x="3" y="3" width="18" height="18"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="9" x2="9" y2="21"/></svg></div>
          <p class="empty-title">KONTACT CATALOG AGENT</p>
          <p class="empty-sub">Ask anything about your uploaded catalogs</p>
          <div class="chip-row">{#each defaultChips as chip}<button class="suggestion-btn" onclick={() => send(chip)}>{chip}</button>{/each}</div>
        </div>
      {/if}

      {#each messages as msg, idx}
        {#if msg.role === 'user'}
          <div class="msg-row msg-row-user animate-fade-up">
            <div class="bubble-user"><p>{msg.content}</p></div>
            <div class="user-avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>
          </div>
          <div class="msg-meta msg-meta-right">{#if msg.timestamp}{msg.timestamp}{/if} · READ</div>
        {:else}
          {#if idx > 0 && messages[idx - 1]?.role === 'user'}
            <div class="cli-exec-bar animate-fade-up">
              <span class="cli-exec-icon">$</span>
              <span class="cli-exec-text">kontact exec --catalog-rag --{modelConfig?.vision_model?.split('/')[1] || 'agent'}</span>
              <span class="cli-exec-stats">{#if msg.sources?.length}&#10003; {msg.sources.length} sources{/if}</span>
            </div>
          {/if}

          <div class="bubble-assistant animate-fade-up">
            <div class="prose-chat">{@html markdownToHtml(msg.content)}</div>

            <!-- Inline citation thumbnails -->
            {#if msg.sources?.length > 0}
              <div class="cite-strip">
                {#each msg.sources as src, si}
                  <button class="cite-thumb" onclick={() => expandedImg = { src: `/api/image/${src.folder}/${src.file}`, alt: `${src.folder} · ${src.file}${src.company ? ' · ' + src.company : ''}` }} title="Click to enlarge">
                    <img src={`/api/image/${src.folder}/${src.file}`} alt={src.file} class="cite-thumb-img" loading="lazy" onerror={(e) => e.target.style.display='none'} />
                    <span class="cite-badge">REF {si + 1}</span>
                  </button>
                {/each}
              </div>
            {/if}

            <!-- Action bar -->
            <div class="action-bar">
              <div class="action-left">
                <span class="action-label">HELPFUL?</span>
                <button class="action-btn" class:feedback-active={feedbackState[idx] === 'up'} title="Yes" aria-label="Helpful" disabled={!!feedbackState[idx]} onclick={() => submitFeedback(idx, 'up')}><svg width="14" height="14" viewBox="0 0 24 24" fill={feedbackState[idx] === 'up' ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>
                <button class="action-btn" class:feedback-active={feedbackState[idx] === 'down'} title="No" aria-label="Not helpful" disabled={!!feedbackState[idx]} onclick={() => submitFeedback(idx, 'down')}><svg width="14" height="14" viewBox="0 0 24 24" fill={feedbackState[idx] === 'down' ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/><path d="M17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/></svg></button>
              </div>
              <div class="action-right">
                <button class="action-btn-label" aria-label="Copy response" onclick={() => copyText(msg.content, idx)}><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="0"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>{copiedIdx === idx ? 'COPIED' : 'COPY'}</button>
                <button class="action-btn-label" aria-label="Save response" onclick={() => exportCSV(msg.content)}><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>SAVE</button>
              </div>
            </div>
          </div>

          <div class="msg-meta msg-meta-left">{#if msg.timestamp}{msg.timestamp}{/if} · AGENT</div>

          {#if idx === messages.length - 1 && !loading}
            <div class="followup-chips animate-fade-up">{#each extractSuggestions(msg.content) as chip}<button class="suggestion-btn" onclick={() => send(chip)}>{chip}</button>{/each}</div>
          {/if}
        {/if}
      {/each}

      <!-- RAG ANALYZING animation -->
      {#if loading && toolSteps.length > 0}
        <div class="rag-card animate-fade-up">
          <div class="rag-header">
            <span class="rag-badge">RAG ANALYZING</span>
            <span class="rag-dots"><span class="dot dot1"></span><span class="dot dot2"></span><span class="dot dot3"></span></span>
          </div>
          <div class="rag-steps">
            {#each toolSteps as step}
              <div class="rag-step">
                {#if step.done}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-5"/></svg>
                {:else}
                  <span class="rag-spinner"></span>
                {/if}
                <span class:rag-done={step.done}>{step.text}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if streamingText}
        <div class="bubble-assistant animate-fade-up"><div class="prose-chat">{@html markdownToHtml(streamingText)}</div></div>
      {/if}

      {#if loading && !streamingText && toolSteps.length === 0}
        <div class="rag-card animate-fade-up">
          <div class="rag-header">
            <span class="rag-badge">RAG ANALYZING</span>
            <span class="rag-dots"><span class="dot dot1"></span><span class="dot dot2"></span><span class="dot dot3"></span></span>
          </div>
          <div class="rag-steps"><div class="rag-step"><span class="rag-spinner"></span><span>Agent is analyzing your question...</span></div></div>
        </div>
      {/if}
    </div>
  </div>

  <div class="input-bar-wrap">
    <div class="input-bar">
      <textarea bind:this={textareaEl} bind:value={input} oninput={autoGrow} onkeydown={handleKeydown} placeholder="Ask about your catalogs..." rows="1"></textarea>
      <button class="voice-btn" class:voice-active={isListening} onclick={toggleVoice} title={isListening ? 'Stop listening' : 'Voice input'} aria-label="Voice input">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="1" width="6" height="11" rx="0"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
      </button>
      {#if loading}
        <button class="stop-btn" onclick={stopStreaming} title="Stop" aria-label="Stop generating"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12"/></svg></button>
      {:else}
        <button class="send-btn" onclick={() => send()} disabled={!input.trim()} aria-label="Send message"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
      {/if}
    </div>
    <div class="footer-disclaimer">KONTACT CATALOG AGENT CAN MAKE MISTAKES. VERIFY CRITICAL INFORMATION.</div>
  </div>
</div>

<style>
  @keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
  .animate-fade-up { animation: fadeUp 0.3s ease-out both; }

  .chat-page { display:flex; flex-direction:column; height:100%; max-height:100%; overflow:hidden; font-family:'Space Grotesk',sans-serif; padding-bottom:56px; box-sizing:border-box; }
  @media (min-width:768px) { .chat-page { padding-bottom:0; } }
  .chat-header { display:flex; justify-content:space-between; align-items:center; padding:10px 16px; border-bottom:2px solid var(--color-on-surface); background:var(--color-surface-bright); flex-shrink:0; }
  .chat-header h1 { font-size:1.25rem; font-weight:700; margin:0; }
  .header-btn { font-family:'Space Grotesk',sans-serif; font-size:0.7rem; font-weight:600; padding:4px 12px; border:2px solid var(--color-on-surface); background:var(--color-surface-bright); cursor:pointer; text-transform:uppercase; letter-spacing:0.05em; min-height:32px; }
  .header-btn:hover,.header-btn.active { background:var(--color-on-surface); color:var(--color-surface); }
  @media (min-width:768px) { .mobile-only { display:none; } }
  .header-btn.new { background:#c6f6a4; border-color:var(--color-on-surface); }
  .header-btn.new:hover { background:#4caf50; color:#fff; }

  .model-bar { display:flex; gap:6px; padding:6px 16px; background:#1a1a1a; flex-wrap:wrap; flex-shrink:0; }
  .model-tag { font-family:'Space Grotesk',monospace; font-size:0.55rem; font-weight:700; padding:3px 10px; letter-spacing:0.04em; text-transform:uppercase; border:1.5px solid; }
  .model-tag.llm { color:#00fc40; border-color:#00fc40; } .model-tag.embed { color:#00b4d8; border-color:#00b4d8; } .model-tag.provider { color:#ffd93d; border-color:#ffd93d; }

  .chat-body { flex:1; display:flex; overflow:hidden; min-height:0; }

  .history-panel { width:240px; flex-shrink:0; border-right:2px solid var(--color-on-surface); background:var(--color-surface-bright); overflow-y:auto; display:none; }
  @media (min-width:768px) { .history-panel { display:block; } }
  .history-panel.show-mobile { display:block; }
  .history-title { font-size:0.65rem; font-weight:900; letter-spacing:0.1em; padding:10px 12px; background:var(--color-on-surface); color:var(--color-surface); text-transform:uppercase; }
  .history-item { display:flex; align-items:center; border-bottom:1px solid rgba(0,0,0,0.08); }
  .history-item.active { background:var(--color-surface-dim); border-left:3px solid var(--color-primary); }
  .history-item-btn { flex:1; text-align:left; padding:10px 12px; background:none; border:none; cursor:pointer; font-family:inherit; min-height:44px; display:flex; flex-direction:column; gap:2px; }
  .history-item-btn:hover { background:var(--color-surface-dim); }
  .history-preview { font-size:0.75rem; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:180px; display:block; }
  .history-meta { font-size:0.6rem; color:var(--color-on-surface-dim); }
  .history-delete { background:none; border:none; font-size:18px; padding:8px; cursor:pointer; color:var(--color-on-surface-dim); min-height:36px; }
  .history-delete:hover { color:var(--color-error); }
  .history-empty { font-size:0.8rem; color:var(--color-on-surface-dim); padding:16px 12px; margin:0; }

  .messages { flex:1; overflow-y:auto; padding:16px 24px; display:flex; flex-direction:column; gap:8px; scroll-behavior:smooth; max-width:900px; margin:0 auto; width:100%; box-sizing:border-box; }
  .empty-state { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; text-align:center; padding:24px 16px; }
  .empty-icon { opacity:0.4; } .empty-title { font-size:1rem; font-weight:900; letter-spacing:0.08em; margin:0; text-transform:uppercase; } .empty-sub { font-size:0.8rem; color:var(--color-on-surface-dim); margin:0; }
  .chip-row { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; }

  .msg-row { display:flex; align-items:flex-start; gap:10px; } .msg-row-user { justify-content:flex-end; }
  .bubble-user { max-width:70%; } .bubble-user p { margin:0; white-space:pre-wrap; }
  .user-avatar { width:36px; height:36px; flex-shrink:0; border:2px solid var(--color-on-surface); display:flex; align-items:center; justify-content:center; background:var(--color-surface-bright); }
  .msg-meta { font-size:0.55rem; font-weight:600; color:var(--color-on-surface-dim); letter-spacing:0.06em; text-transform:uppercase; margin-bottom:8px; font-family:'Space Grotesk',monospace; }
  .msg-meta-right { text-align:right; padding-right:50px; } .msg-meta-left { padding-left:4px; }

  .bubble-assistant { align-self:flex-start; max-width:88%; overflow:visible !important; max-height:none !important; }

  .cli-exec-bar { display:flex; align-items:center; gap:8px; background:#1a1a1a; color:#8a8a9a; padding:8px 14px; font-family:'Space Grotesk',monospace; font-size:0.7rem; border:2px solid var(--color-on-surface); margin-bottom:4px; }
  .cli-exec-icon { color:#00fc40; font-weight:700; } .cli-exec-text { color:#e0e0e0; flex:1; } .cli-exec-stats { color:#00fc40; font-weight:700; }

  /* RAG Analyzing card */
  .rag-card { background:var(--color-surface-dim); border:2px solid var(--color-on-surface); border-right-width:4px; border-bottom-width:4px; padding:14px 16px; max-width:500px; }
  .rag-header { display:flex; align-items:center; gap:10px; padding-bottom:8px; border-bottom:1px solid rgba(0,0,0,0.1); margin-bottom:10px; }
  .rag-badge { font-size:0.7rem; font-weight:900; letter-spacing:0.08em; text-transform:uppercase; background:var(--color-primary-container); color:#000; padding:3px 10px; border:2px solid var(--color-on-surface); }
  .rag-dots { display:flex; gap:4px; align-items:center; }
  .dot { width:8px; height:8px; border-radius:50% !important; }
  .dot1 { background:#16a34a; } .dot2 { background:#f59e0b; } .dot3 { background:#dc2626; }
  .rag-steps { display:flex; flex-direction:column; gap:8px; }
  .rag-step { display:flex; align-items:center; gap:8px; font-size:0.85rem; font-family:'Space Grotesk',monospace; }
  .rag-done { color:var(--color-on-surface-dim); }
  .rag-spinner { width:16px; height:16px; border:2px solid rgba(0,0,0,0.15); border-top-color:var(--color-primary); border-radius:50% !important; animation:spin 0.8s linear infinite; flex-shrink:0; }
  @keyframes spin { to { transform:rotate(360deg); } }

  /* Citation thumbnails — small clickable strip */
  .cite-strip { display:flex; gap:6px; margin-top:10px; padding-top:8px; border-top:1px dashed rgba(0,0,0,0.12); overflow-x:auto; -webkit-overflow-scrolling:touch; }
  .cite-thumb { flex-shrink:0; width:72px; border:2px solid var(--color-on-surface); background:var(--color-surface-bright); cursor:pointer; padding:0; position:relative; transition:transform 0.15s; }
  .cite-thumb:hover { transform:translateY(-2px); box-shadow:3px 3px 0 var(--color-on-surface); }
  .cite-thumb-img { width:100%; height:52px; object-fit:cover; display:block; }
  .cite-badge { display:block; font-size:0.45rem; font-weight:900; letter-spacing:0.06em; background:var(--color-on-surface); color:var(--color-surface); padding:2px 0; text-align:center; text-transform:uppercase; }

  /* Lightbox */
  .lightbox { position:fixed; inset:0; background:rgba(0,0,0,0.85); z-index:9999; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:12px; cursor:pointer; }
  .lightbox-img { max-width:90vw; max-height:80vh; object-fit:contain; border:3px solid #fff; }
  .lightbox-caption { color:#fff; font-size:0.8rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; font-family:'Space Grotesk',monospace; }
  .lightbox-close { position:absolute; top:20px; right:20px; background:none; border:2px solid #fff; color:#fff; font-size:24px; width:40px; height:40px; cursor:pointer; display:flex; align-items:center; justify-content:center; min-height:40px; }

  .action-bar { display:flex; align-items:center; justify-content:space-between; margin-top:10px; padding-top:8px; border-top:1px solid rgba(0,0,0,0.1); flex-wrap:wrap; gap:6px; }
  .action-left { display:flex; align-items:center; gap:6px; } .action-right { display:flex; align-items:center; gap:4px; }
  .action-label { font-size:0.6rem; font-weight:700; color:var(--color-on-surface-dim); letter-spacing:0.06em; text-transform:uppercase; }
  .action-btn { background:none; border:1px solid var(--color-on-surface); padding:4px 6px; cursor:pointer; min-height:28px; display:flex; align-items:center; color:var(--color-on-surface-dim); }
  .action-btn:hover:not(:disabled) { background:var(--color-surface-dim); color:var(--color-on-surface); }
  .action-btn:disabled { opacity:0.5; cursor:not-allowed; }
  .action-btn.feedback-active { background:var(--color-primary); color:var(--color-on-surface); border-color:var(--color-primary); opacity:1; }
  .action-btn-label { font-family:'Space Grotesk',sans-serif; font-size:0.6rem; font-weight:700; padding:4px 10px; border:1px solid var(--color-on-surface); background:none; cursor:pointer; text-transform:uppercase; letter-spacing:0.04em; color:var(--color-on-surface-dim); min-height:28px; display:inline-flex; align-items:center; gap:4px; }
  .action-btn-label:hover { background:var(--color-on-surface); color:var(--color-surface); }
  .action-btn-label:hover svg { stroke:var(--color-surface); }

  .followup-chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; margin-bottom:16px; }
  .chip-row { display:flex; flex-wrap:wrap; gap:8px; }

  .input-bar-wrap { border-top:2px solid var(--color-on-surface); background:var(--color-surface-bright); flex-shrink:0; }
  .input-bar { display:flex; align-items:flex-end; gap:8px; padding:10px 16px; max-width:900px; margin:0 auto; width:100%; box-sizing:border-box; }
  .input-bar textarea { flex:1; resize:none; font-family:'Space Grotesk',sans-serif; font-size:0.9rem; padding:10px 12px; border:2px solid var(--color-on-surface); background:var(--color-surface); line-height:1.4; min-height:40px; max-height:80px; overflow-y:auto; color:var(--color-on-surface); }
  .input-bar textarea:focus { outline:none; border-color:var(--color-primary); }
  .input-bar textarea::placeholder { color:var(--color-on-surface-dim); text-transform:uppercase; letter-spacing:0.05em; font-size:0.75rem; }
  .voice-btn { width:36px; height:36px; display:flex; align-items:center; justify-content:center; border:2px solid var(--color-on-surface); background:none; color:var(--color-on-surface-dim); cursor:pointer; flex-shrink:0; min-height:36px; }
  .voice-btn:hover { background:var(--color-surface-dim); }
  .voice-active { background:var(--color-error) !important; border-color:var(--color-error) !important; color:#fff !important; }

  .stop-btn { width:44px; height:44px; display:flex; align-items:center; justify-content:center; border:2px solid var(--color-error); background:var(--color-error); color:#fff; cursor:pointer; flex-shrink:0; min-height:44px; }
  .stop-btn:hover { opacity:0.8; }
  .footer-disclaimer { text-align:center; font-size:0.55rem; color:var(--color-on-surface-dim); padding:4px 16px 8px; letter-spacing:0.04em; text-transform:uppercase; }
  @media (max-width:767px) { .footer-disclaimer { display:none; } }

  @media (max-width:640px) {
    .history-panel { width:180px; } .history-preview { max-width:130px; }
    .bubble-user { max-width:88%; } .bubble-assistant { max-width:95%; }
    .action-bar { flex-direction:column; align-items:flex-start; }
    .msg-meta-right { padding-right:50px; } .user-avatar { width:30px; height:30px; }
    .rag-card { max-width:100%; }
  }

  /* History search */
  .history-search-wrap { padding:8px 8px 4px; }
  .history-search { width:100%; font-family:'Space Grotesk',sans-serif; font-size:0.7rem; padding:6px 8px; border:2px solid var(--color-on-surface); background:var(--color-surface); color:var(--color-on-surface); box-sizing:border-box; }
  .history-search:focus { outline:none; border-color:var(--color-primary); }
  .history-search::placeholder { color:var(--color-on-surface-dim); text-transform:uppercase; letter-spacing:0.04em; font-size:0.6rem; }

  /* Voice input button */
  .voice-btn { width:44px; height:44px; display:flex; align-items:center; justify-content:center; border:2px solid var(--color-on-surface); background:var(--color-surface-bright); cursor:pointer; flex-shrink:0; min-height:44px; color:var(--color-on-surface); transition:background 0.15s, color 0.15s; }
  .voice-btn:hover { background:var(--color-surface-dim); }
  .voice-btn.voice-active { background:#dc2626; border-color:#dc2626; color:#fff; }
  .voice-btn.voice-active svg { stroke:#fff; }
</style>
