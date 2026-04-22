<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  let { children } = $props();

  // Theme
  let theme = $state<'light' | 'dark'>('light');

  function toggleTheme() {
    theme = theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('kontact_theme', theme);
  }

  // Navigation
  const currentPath = $derived($page.url.pathname);

  const tabs = [
    { path: '/upload', label: 'Upload', iconId: 'camera' },
    { path: '/queue', label: 'Queue', iconId: 'list' },
    { path: '/chat', label: 'Agent', iconId: 'message' },
    { path: '/data', label: 'Data', iconId: 'data' },
    { path: '/more', label: 'More', iconId: 'menu' }
  ] as const;

  function isActive(tabPath: string): boolean {
    if (tabPath === '/upload') return currentPath === '/' || currentPath.startsWith('/upload');
    return currentPath.startsWith(tabPath);
  }

  function navigateTo(path: string) {
    goto(path);
  }

  onMount(() => {
    const saved = localStorage.getItem('kontact_theme');
    if (saved === 'dark' || saved === 'light') {
      theme = saved;
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      theme = 'dark';
    }
    document.documentElement.setAttribute('data-theme', theme);
  });
</script>

<div class="app-shell">
  <!-- Desktop Sidebar (hidden on mobile) -->
  <aside class="sidebar">
    <div class="sidebar-logo">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <rect x="3" y="3" width="18" height="18"/>
        <line x1="3" y1="9" x2="21" y2="9"/>
        <line x1="9" y1="9" x2="9" y2="21"/>
      </svg>
      <span>KONTACT</span>
    </div>

    <nav class="sidebar-nav">
      <!-- Upload -->
      <button class:active={isActive('/upload')} onclick={() => navigateTo('/upload')} aria-label="Upload">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18"/>
          <circle cx="12" cy="13" r="4"/>
          <line x1="12" y1="3" x2="12" y2="5"/>
        </svg>
        <span>Upload</span>
      </button>

      <!-- Queue -->
      <button class:active={isActive('/queue')} onclick={() => navigateTo('/queue')} aria-label="Queue">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="8" y1="6" x2="21" y2="6"/>
          <line x1="8" y1="12" x2="21" y2="12"/>
          <line x1="8" y1="18" x2="21" y2="18"/>
          <line x1="3" y1="6" x2="3.01" y2="6"/>
          <line x1="3" y1="12" x2="3.01" y2="12"/>
          <line x1="3" y1="18" x2="3.01" y2="18"/>
        </svg>
        <span>Queue</span>
      </button>

      <!-- Chat -->
      <button class:active={isActive('/chat')} onclick={() => navigateTo('/chat')} aria-label="Agent chat">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span>Agent</span>
      </button>

      <!-- Data -->
      <button class:active={isActive('/data')} onclick={() => navigateTo('/data')} aria-label="Data">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="3" width="20" height="5"/>
          <rect x="2" y="10" width="20" height="5"/>
          <rect x="2" y="17" width="20" height="5"/>
        </svg>
        <span>Data</span>
      </button>

      <!-- More -->
      <button class:active={isActive('/more')} onclick={() => navigateTo('/more')} aria-label="More options">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
        <span>More</span>
      </button>
    </nav>

    <div class="sidebar-footer">
    </div>
  </aside>

  <div class="app-main">
    <!-- Mobile Top Header Bar (hidden on desktop) -->
    <header class="mobile-header dark-title-bar">
      <div style="display: flex; align-items: center; gap: 8px;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <rect x="3" y="3" width="18" height="18"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="9" y1="9" x2="9" y2="21"/>
        </svg>
        <span style="font-size: 18px; font-weight: 900; letter-spacing: 0.08em;">KONTACT</span>
      </div>

    </header>

    <!-- Page Content -->
    <main class="page-content" class:is-chat={currentPath.startsWith('/chat')}>
      {@render children()}
    </main>

    <!-- Bottom Navigation Bar (Mobile only) -->
    <nav class="nav-bottom">
      <button class:active={isActive('/upload')} onclick={() => navigateTo('/upload')} aria-label="Upload">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18"/><circle cx="12" cy="13" r="4"/><line x1="12" y1="3" x2="12" y2="5"/>
        </svg>
        <span>Upload</span>
      </button>
      <button class:active={isActive('/queue')} onclick={() => navigateTo('/queue')} aria-label="Queue">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
          <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
        </svg>
        <span>Queue</span>
      </button>
      <button class:active={isActive('/chat')} onclick={() => navigateTo('/chat')} aria-label="Agent chat">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span>Agent</span>
      </button>
      <button class:active={isActive('/data')} onclick={() => navigateTo('/data')} aria-label="Browse data">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="3" width="20" height="5"/><rect x="2" y="10" width="20" height="5"/><rect x="2" y="17" width="20" height="5"/>
        </svg>
        <span>Data</span>
      </button>
      <button class:active={isActive('/more')} onclick={() => navigateTo('/more')} aria-label="More options">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
        <span>More</span>
      </button>
    </nav>
  </div>
</div>

<style>
  /* ── App Shell ── */
  .app-shell {
    display: flex;
    height: 100vh;
    height: 100dvh;
    overflow: hidden;
  }

  .app-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
    min-width: 0;
    overflow: hidden;
  }

  .page-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    padding-bottom: calc(56px + 16px + env(safe-area-inset-bottom, 0px));
  }

  .page-content.is-chat {
    padding: 0;
    overflow: hidden;
    position: relative;
  }

  /* ── Sidebar (desktop only) ── */
  .sidebar {
    display: none;
  }

  /* ── Mobile header ── */
  .mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    flex-shrink: 0;
  }

  /* ── Desktop: show sidebar, hide mobile header ── */
  @media (min-width: 768px) {
    .sidebar {
      display: flex;
      flex-direction: column;
      width: 200px;
      flex-shrink: 0;
      background: var(--color-on-surface);
      color: var(--color-surface);
      border-right: 3px solid var(--color-on-surface);
    }

    .sidebar-logo {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      font-size: 16px;
      font-weight: 900;
      letter-spacing: 0.08em;
      border-bottom: 1px solid rgba(255,255,255,0.15);
    }

    .sidebar-nav {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 8px 0;
    }

    .sidebar-nav button {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 16px;
      background: none;
      border: none;
      color: rgba(255,255,255,0.5);
      font-family: var(--font-family-display);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      cursor: pointer;
      transition: background 0.1s, color 0.1s;
      min-height: 44px;
      border-left: 3px solid transparent;
    }

    .sidebar-nav button:hover {
      background: rgba(255,255,255,0.08);
      color: rgba(255,255,255,0.8);
    }

    .sidebar-nav button.active {
      color: var(--color-primary-container);
      background: rgba(255,255,255,0.05);
      border-left-color: var(--color-primary-container);
    }

    .sidebar-footer {
      padding: 12px 16px;
      border-top: 1px solid rgba(255,255,255,0.15);
    }

    .theme-btn {
      display: flex;
      align-items: center;
      gap: 8px;
      background: none;
      border: 1px solid rgba(255,255,255,0.3);
      color: rgba(255,255,255,0.6);
      padding: 8px 12px;
      font-family: var(--font-family-display);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      cursor: pointer;
      width: 100%;
      min-height: 36px;
    }

    .theme-btn:hover {
      background: rgba(255,255,255,0.1);
      color: rgba(255,255,255,0.9);
    }

    .mobile-header {
      display: none;
    }

    .page-content {
      padding: 24px 32px;
      padding-bottom: 32px;
      max-width: none;
    }
  }

  @media (min-width: 1200px) {
    .sidebar {
      width: 220px;
    }
  }
</style>
