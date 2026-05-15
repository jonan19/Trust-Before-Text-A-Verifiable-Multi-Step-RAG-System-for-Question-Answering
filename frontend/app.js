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
        const stats = await response.json();
        totalChunksEl.textContent = stats.total_chunks || 0;
        uniqueDocsEl.textContent = stats.unique_documents || 0;
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
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
        renderResults(data);
    } catch (error) {
        showNotification('Error performing search', 'error');
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

    showNotification(`Uploading ${file.name}...`, 'success');
    
    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        showNotification(data.message, 'success');
        await updateStats();
    } catch (error) {
        showNotification('Upload failed', 'error');
        console.error('Upload error:', error);
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
    const { chunks, similarity_scores } = data;
    resultsCount.textContent = `${chunks.length} Results`;

    if (chunks.length === 0) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">❓</div>
                <h3>No relevant evidence found</h3>
                <p>Try rephrasing your question or adding more context.</p>
            </div>
        `;
        return;
    }

    resultsContainer.innerHTML = chunks.map((chunk, i) => `
        <div class="result-card" style="animation-delay: ${i * 0.1}s">
            <div class="result-card-header">
                <span class="source-tag">${chunk.source_document}</span>
                <span class="score-tag">Similarity: ${(similarity_scores[i] * 100).toFixed(1)}%</span>
            </div>
            <div class="result-text">${chunk.text}</div>
        </div>
    `).join('');
}

function setLoading(isLoading) {
    isSearching = isLoading;
    queryBtn.disabled = isLoading;
    queryBtn.innerHTML = isLoading ? '<span class="loader"></span>' : 'Search';
    queryInput.disabled = isLoading;
}

function showNotification(message, type = 'success') {
    const note = document.createElement('div');
    note.className = `notification ${type}`;
    note.textContent = message;
    notificationContainer.appendChild(note);
    
    setTimeout(() => {
        note.style.opacity = '0';
        setTimeout(() => note.remove(), 300);
    }, 3000);
}

// Start app
init();
