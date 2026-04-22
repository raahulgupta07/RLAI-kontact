<script>
  import { goto } from '$app/navigation';

  let files = $state([]);
  let warnings = $state([]);
  function generateId() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID().slice(0, 8);
    return Math.random().toString(36).slice(2, 10);
  }
  let batchName = $state(generateId());
  let uploading = $state('idle');
  let result = $state(null);
  let fileInput;
  let uploadError = $state('');
  let uploadProgress = $state(0);

  function checkImageQuality(fileList) {
    for (const file of fileList) {
      if (file.size < 10000) {
        warnings = [...warnings, { name: file.name, reason: `too small (${(file.size / 1024).toFixed(1)}KB)` }];
        continue;
      }
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        if (img.width < 200 || img.height < 200) {
          warnings = [...warnings, { name: file.name, reason: `low resolution (${img.width}x${img.height}px)` }];
        }
        URL.revokeObjectURL(url);
      };
      img.onerror = () => URL.revokeObjectURL(url);
      img.src = url;
    }
  }

  function handleFiles(event) {
    const selected = Array.from(event.target.files ?? []);
    files = [...files, ...selected];
    checkImageQuality(selected);
  }

  function handleDrop(event) {
    event.preventDefault();
    const dropped = Array.from(event.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    files = [...files, ...dropped];
    checkImageQuality(dropped);
  }

  function handleDragOver(event) {
    event.preventDefault();
  }

  function removeFile(index) {
    const removed = files[index];
    files = files.filter((_, i) => i !== index);
    if (removed) {
      warnings = warnings.filter(w => w.name !== removed.name);
    }
  }

  function getThumbnailUrl(file) {
    return URL.createObjectURL(file);
  }

  async function upload() {
    if (files.length === 0 || uploading === 'uploading') return;
    uploading = 'uploading';
    uploadError = '';
    uploadProgress = 0;
    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append('files', file);
      }
      if (batchName) {
        formData.append('batch_id', batchName);
      }
      const res = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            uploadProgress = Math.round((e.loaded / e.total) * 100);
          }
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try { resolve(JSON.parse(xhr.responseText)); } catch { resolve({}); }
          } else {
            reject(new Error(`Upload failed (${xhr.status})`));
          }
        };
        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.open('POST', '/api/upload');
        xhr.send(formData);
      });
      result = res;
      uploading = 'done';
    } catch (err) {
      console.error('Upload failed:', err);
      uploadError = err instanceof Error ? err.message : 'Upload failed. Please try again.';
      uploading = 'idle';
    }
  }
</script>

<svelte:head>
  <title>UPLOAD | KONTACT</title>
</svelte:head>

<div class="upload-page">
  <div class="dark-title-bar">
    <h1>UPLOAD CATALOG</h1>
  </div>

  {#if uploading === 'done' && result}
    <!-- SUCCESS STATE -->
    <div class="success-block ink-border stamp-shadow">
      <div class="success-icon">&#10003;</div>
      <p class="success-text">BATCH UPLOADED</p>
      <p class="batch-id tag-label">ID: {result.batch_id ?? batchName}</p>
      <p class="file-count">{files.length} image{files.length !== 1 ? 's' : ''} sent for processing</p>
      <button class="send-btn" onclick={() => goto('/queue')}>
        VIEW QUEUE &rarr;
      </button>
      <button class="reset-btn ink-border" onclick={() => {
        files = [];
        warnings = [];
        batchName = generateId();
        uploading = 'idle';
        result = null;
      }}>
        UPLOAD MORE
      </button>
    </div>
  {:else}
    <!-- UPLOAD ERROR BANNER -->
    {#if uploadError}
      <div class="upload-error ink-border">
        <p class="upload-error-text">&#9888; {uploadError}</p>
        <button class="upload-error-dismiss" onclick={() => uploadError = ''}>&times;</button>
      </div>
    {/if}

    <!-- DROP ZONE -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="drop-zone ink-border stamp-shadow"
      onclick={() => fileInput.click()}
      onkeydown={(e) => { if (e.key === 'Enter') fileInput.click(); }}
      ondrop={handleDrop}
      ondragover={handleDragOver}
      role="button"
      tabindex="0"
    >
      <div class="drop-icon">&#128247;</div>
      <p class="drop-label">TAP TO TAKE PHOTO<br/>OR SELECT IMAGES</p>
      <p class="drop-hint">drop files here on desktop</p>
    </div>

    <input
      bind:this={fileInput}
      type="file"
      accept="image/*"
      capture="environment"
      multiple
      onchange={handleFiles}
      class="file-input-hidden"
    />

    <!-- IMAGE QUALITY WARNINGS -->
    {#if warnings.length > 0}
      <div class="quality-warnings ink-border">
        {#each warnings as w}
          <p class="quality-warning-item">&#9888; {w.name} may be {w.reason}</p>
        {/each}
      </div>
    {/if}

    <!-- THUMBNAIL STRIP -->
    {#if files.length > 0}
      <div class="thumb-strip">
        {#each files as file, i}
          <div class="thumb-item">
            <img src={getThumbnailUrl(file)} alt={file.name} class="thumb-img" />
            <button class="thumb-remove" onclick={() => removeFile(i)}>&times;</button>
          </div>
        {/each}
      </div>
    {/if}

    <!-- BATCH NAME -->
    <div class="field-group">
      <label class="field-label tag-label" for="batch-name">BATCH NAME</label>
      <input
        id="batch-name"
        type="text"
        class="field-input ink-border"
        bind:value={batchName}
        placeholder="e.g. catalog-spring"
      />
    </div>

    <!-- UPLOAD BUTTON -->
    <button
      class="send-btn upload-action"
      onclick={upload}
      disabled={files.length === 0 || uploading === 'uploading'}
    >
      {#if uploading === 'uploading'}
        UPLOADING...
      {:else}
        UPLOAD {files.length} IMAGE{files.length !== 1 ? 'S' : ''}
      {/if}
    </button>

    {#if uploading === 'uploading'}
      <div class="progress-bar ink-border">
        <div class="progress-fill" style="width: {uploadProgress}%"></div>
      </div>
      <p class="progress-label">{uploadProgress}%</p>
    {/if}
  {/if}
</div>

<style>
  .upload-page {
    font-family: 'Space Grotesk', sans-serif;
    max-width: 600px;
    margin: 0 auto;
    padding: 0 16px 32px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* ---- DROP ZONE ---- */
  .drop-zone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    border: 3px dashed #000;
    background: #f5f5f0;
    cursor: pointer;
    padding: 32px 16px;
    text-align: center;
    -webkit-tap-highlight-color: transparent;
    transition: background 0.15s;
  }
  .drop-zone:active {
    background: #e8e8e0;
  }
  .drop-icon {
    font-size: 48px;
    line-height: 1;
    margin-bottom: 12px;
  }
  .drop-label {
    font-weight: 700;
    font-size: 16px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin: 0;
  }
  .drop-hint {
    font-size: 12px;
    color: #888;
    margin: 8px 0 0;
    text-transform: lowercase;
  }

  .file-input-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  /* ---- QUALITY WARNINGS ---- */
  .quality-warnings {
    background: #fff8e1;
    border: 2px solid #000;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .quality-warning-item {
    font-family: 'Space Grotesk', monospace;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: #7a6200;
    margin: 0;
    line-height: 1.4;
  }

  /* ---- THUMBNAIL STRIP ---- */
  .thumb-strip {
    display: flex;
    overflow-x: auto;
    gap: 12px;
    padding: 8px 0;
    -webkit-overflow-scrolling: touch;
  }
  .thumb-item {
    position: relative;
    flex-shrink: 0;
    width: 80px;
    height: 80px;
    border: 2px solid #000;
  }
  .thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .thumb-remove {
    position: absolute;
    top: -8px;
    right: -8px;
    width: 24px;
    height: 24px;
    background: #000;
    color: #fff;
    border: 2px solid #fff;
    font-size: 16px;
    font-weight: 700;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    padding: 0;
    border-radius: 0;
  }

  /* ---- FIELD ---- */
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .field-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .field-input {
    font-family: 'Space Grotesk', monospace;
    font-size: 16px;
    padding: 12px;
    border: 2px solid #000;
    background: #fff;
    border-radius: 0;
    outline: none;
    width: 100%;
    box-sizing: border-box;
  }
  .field-input:focus {
    box-shadow: 4px 4px 0 #000;
  }

  /* ---- UPLOAD BUTTON ---- */
  .upload-action {
    width: 100%;
    min-height: 56px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border: 2px solid #000;
    border-radius: 0;
    cursor: pointer;
    background: #d4e4bc;
    color: #000;
    transition: box-shadow 0.1s, transform 0.1s;
  }
  .upload-action:active:not(:disabled) {
    transform: translate(2px, 2px);
    box-shadow: none;
  }
  .upload-action:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* ---- PROGRESS ---- */
  .progress-bar {
    height: 12px;
    border: 2px solid #000;
    background: #fff;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: #000;
    transition: width 0.2s ease;
  }
  .progress-label {
    font-family: 'Space Grotesk', monospace;
    font-size: 12px;
    font-weight: 700;
    text-align: center;
    margin: 0;
    letter-spacing: 0.04em;
  }

  /* ---- UPLOAD ERROR ---- */
  .upload-error {
    background: #fde8e8;
    border: 2px solid #b91c1c;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .upload-error-text {
    font-family: 'Space Grotesk', monospace;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: #b91c1c;
    margin: 0;
    line-height: 1.4;
  }
  .upload-error-dismiss {
    background: none;
    border: none;
    font-size: 18px;
    font-weight: 700;
    color: #b91c1c;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }

  /* ---- SUCCESS ---- */
  .success-block {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 32px 16px;
    border: 2px solid #000;
    background: #f5f5f0;
    text-align: center;
  }
  .success-icon {
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
  }
  .success-text {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.06em;
    margin: 0;
  }
  .batch-id {
    font-family: 'Space Grotesk', monospace;
    font-size: 14px;
    background: #000;
    color: #fff;
    padding: 4px 10px;
    margin: 0;
  }
  .file-count {
    font-size: 14px;
    color: #555;
    margin: 0;
  }
  .reset-btn {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 10px 24px;
    background: #fff;
    border: 2px solid #000;
    border-radius: 0;
    cursor: pointer;
    margin-top: 4px;
  }
  .reset-btn:active {
    background: #eee;
  }
</style>
