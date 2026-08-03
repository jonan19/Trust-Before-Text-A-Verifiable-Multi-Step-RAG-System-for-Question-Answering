const API_BASE_URL = 'http://localhost:8000';

// DOM Elements
const queryInput = document.getElementById('query-input');
const queryBtn = document.getElementById('query-btn');
const resultsContainer = document.getElementById('results-container');
const resultsCount = document.getElementById('results-count');
const totalChunksEl = document.getElementById('total-chunks');
const uniqueDocsEl = document.getElementById('unique-docs');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const resetBtn = document.getElementById('reset-btn');
const notificationContainer = document.getElementById('notification-container');

// State
let isSearching = false;
let apiOnline = true;

// Initialize
async function init() {
    await updateStats();

    // Event Listeners
    queryBtn.addEventListener('click', handleQuery);
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleQuery();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    resetBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to reset the index? This will delete all indexed documents.')) {
            await resetIndex();
        }
    });

    // Drag and Drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('active');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('active');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('active');
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });
}

// API Calls
async function updateStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const stats = await response.json();
        totalChunksEl.textContent = stats.total_chunks || 0;
        uniqueDocsEl.textContent = stats.unique_documents || 0;
        setApiStatus(true);
        await updateDocumentList();
    } catch (error) {
        setApiStatus(false);
        console.error('Error fetching stats:', error);
    }
}

function setApiStatus(online) {
    apiOnline = online;
    let badge = document.getElementById('api-status-badge');
    if (!badge) {
        badge = document.createElement('div');
        badge.id = 'api-status-badge';
        badge.className = 'api-status-badge';
        const statsContainer = document.getElementById('stats-container');
        statsContainer.parentNode.insertBefore(badge, statsContainer.nextSibling);
    }
    if (online) {
        badge.className = 'api-status-badge online';
        badge.textContent = '● API online';
    } else {
        badge.className = 'api-status-badge offline';
        badge.textContent = '● API offline — start api.py';
        totalChunksEl.textContent = '—';
        uniqueDocsEl.textContent = '—';
    }
}

async function updateDocumentList() {
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        if (!response.ok) return;
        const data = await response.json();
        renderDocumentList(data.documents || []);
    } catch (_) { /* silently skip */ }
}

function renderDocumentList(docs) {
    let listEl = document.getElementById('document-list');
    if (!listEl) return;
    listEl.innerHTML = '';
    if (docs.length === 0) {
        listEl.innerHTML = '<li class="doc-list-empty">No documents indexed yet</li>';
        return;
    }
    docs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'doc-list-item';
        const name = document.createElement('span');
        name.className = 'doc-name';
        name.textContent = doc.filename;
        const chunks = document.createElement('span');
        chunks.className = 'doc-chunks';
        chunks.textContent = doc.chunks ? `${doc.chunks} chunks` : '';
        li.appendChild(name);
        li.appendChild(chunks);
        listEl.appendChild(li);
    });
}

async function handleQuery() {
    const query = queryInput.value.trim();
    if (!query || isSearching) return;

    setLoading(true);
    try {
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, k: 5 })
        });
        const data = await response.json();
        if (!response.ok) {
            // Backend returned an error (e.g. 500) — surface the message
            const detail = data.detail || `HTTP ${response.status}`;
            showNotification(`Search error: ${detail}`, 'error');
            console.error('Backend error:', detail);
            return;
        }
        renderResults(data);
    } catch (error) {
        showNotification(`Error performing search: ${error.message}`, 'error');
        console.error('Search error:', error);
    } finally {
        setLoading(false);
    }
}

async function uploadFile(file) {
    const allowedExtensions = ['.txt', '.pdf', '.docx'];
    if (!allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext))) {
        showNotification('Only .txt, .pdf, and .docx files are supported', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    // Show a persistent "indexing" notification — ingestion can take ~60s
    const indexingNote = showNotification(
        `⏳ Indexing ${file.name} — this may take up to a minute…`,
        'info',
        0   // 0 = don't auto-dismiss
    );
    dropZone.style.pointerEvents = 'none';
    dropZone.style.opacity = '0.5';

    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (response.ok) {
            const chunkInfo = data.num_chunks ? ` (${data.num_chunks} chunks indexed)` : '';
            showNotification(`✅ ${file.name} uploaded successfully${chunkInfo}`, 'success');
        } else {
            showNotification(`❌ Upload failed: ${data.detail || 'Unknown error'}`, 'error');
        }
        await updateStats();
    } catch (error) {
        showNotification('❌ Upload failed — is the API server running?', 'error');
        console.error('Upload error:', error);
    } finally {
        // Always remove the indexing spinner and restore the drop zone
        if (indexingNote && indexingNote.parentNode) indexingNote.remove();
        dropZone.style.pointerEvents = '';
        dropZone.style.opacity = '';
        fileInput.value = '';  // allow re-uploading the same file
    }
}

async function resetIndex() {
    try {
        const response = await fetch(`${API_BASE_URL}/reset`, { method: 'DELETE' });
        const data = await response.json();
        showNotification(data.message, 'success');
        await updateStats();
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <h3>No evidence retrieved yet</h3>
                <p>Ask a question or upload a document to get started.</p>
            </div>
        `;
        resultsCount.textContent = '0 Results';
    } catch (error) {
        showNotification('Reset failed', 'error');
    }
}

// UI Helpers
function renderResults(data) {
    const chunks = data.chunks || [];
    const similarity_scores = data.similarity_scores || [];
    const raw_scores = data.raw_scores || [];

    resultsCount.textContent = `${chunks.length} Results`;

    let html = '';

    // Render synthesized answer if present
    if (data.answer) {
        const isAbstain = data.status === 'abstain';
        const statusClass = isAbstain ? 'abstain' : 'success';
        const statusLabel = isAbstain ? 'ABSTAINED' : 'RESOLVED';

        let reasonLabel = '';
        if (isAbstain && data.abstention_reason) {
            reasonLabel = `<span class="abstain-reason-badge">Reason: ${data.abstention_reason}</span>`;
        }

        // Build conflict citations block if sources are available
        let citationsBlock = '';
        if (isAbstain && data.abstention_reason === 'conflict' && data.citations && data.citations.length > 0) {
            const citationItems = data.citations.map(c =>
                `<li><span class="citation-source">${c.source}</span> <span class="citation-score">(score: ${(c.score * 100).toFixed(1)}%)</span></li>`
            ).join('');
            citationsBlock = `
            <div class="conflict-citations">
                <span class="conflict-label">⚠️ Conflicting sources:</span>
                <ul class="citation-list">${citationItems}</ul>
            </div>`;
        }

        html += `
        <div class="answer-card ${statusClass}">
            <div class="answer-card-header">
                <div class="answer-header-left">
                    <span class="answer-title">Synthesized Answer</span>
                    ${reasonLabel}
                </div>
                <span class="status-badge ${statusClass}">${statusLabel}</span>
            </div>
            <div class="answer-text">${data.answer.replace(/\n/g, '<br>')}</div>
            ${citationsBlock}
        </div>
        `;
    }

    if (chunks.length === 0 && !data.answer) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">❓</div>
                <h3>No relevant evidence found</h3>
                <p>Try rephrasing your question or adding more context.</p>
            </div>
        `;
        return;
    }

    // Safely build evidence cards using DOM API to avoid XSS from chunk text
    const fragment = document.createDocumentFragment();

    // Prepend the answer/abstain card if present
    if (html) {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = html;
        fragment.appendChild(wrapper);
    }

    chunks.forEach((chunk, i) => {
        const calibrated = (similarity_scores[i] * 100).toFixed(1);
        const raw = (raw_scores && raw_scores[i]) ? (raw_scores[i] * 100).toFixed(1) : null;

        const card = document.createElement('div');
        card.className = 'result-card';
        card.style.animationDelay = `${i * 0.1}s`;

        const header = document.createElement('div');
        header.className = 'result-card-header';

        const sourceTag = document.createElement('span');
        sourceTag.className = 'source-tag';
        sourceTag.textContent = chunk.source_document || chunk.source || 'unknown';

        const scoreTag = document.createElement('span');
        scoreTag.className = 'score-tag';
        scoreTag.innerHTML = raw
            ? `Score: ${calibrated}% <span class="raw-score">(raw: ${raw}%)</span>`
            : `Similarity: ${calibrated}%`;

        header.appendChild(sourceTag);
        header.appendChild(scoreTag);

        const textEl = document.createElement('div');
        textEl.className = 'result-text';
        textEl.textContent = chunk.text;  // safe: no HTML injection

        card.appendChild(header);
        card.appendChild(textEl);
        fragment.appendChild(card);
    });

    resultsContainer.innerHTML = '';
    resultsContainer.appendChild(fragment);
}

function setLoading(isLoading) {
    isSearching = isLoading;
    queryBtn.disabled = isLoading;
    queryBtn.innerHTML = isLoading ? '<span class="loader"></span>' : 'Search';
    queryInput.disabled = isLoading;
}

function showNotification(message, type = 'success', duration = 3000) {
    const note = document.createElement('div');
    note.className = `notification ${type}`;
    note.textContent = message;
    notificationContainer.appendChild(note);

    if (duration > 0) {
        setTimeout(() => {
            note.style.opacity = '0';
            setTimeout(() => note.remove(), 300);
        }, duration);
    }

    // Return the element so callers can remove persistent notifications manually
    return note;
}

// Start app
init();
