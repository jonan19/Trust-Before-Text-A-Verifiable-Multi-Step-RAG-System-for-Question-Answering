const API_BASE_URL = 'http://localhost:8000';

// DOM Elements
const queryInput = document.getElementById('query-input');
const queryBtn = document.getElementById('query-btn');
const totalChunksEl = document.getElementById('total-chunks');
const uniqueDocsEl = document.getElementById('unique-docs');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const resetBtn = document.getElementById('reset-btn');
const notificationContainer = document.getElementById('notification-container');

const traceState = document.getElementById('trace-state');
const traceNodes = document.getElementById('trace-nodes');
const traceDetail = document.getElementById('trace-detail');
const outcomeBay = document.getElementById('outcome-bay');
const evidenceBay = document.getElementById('evidence-bay');
const rawBay = document.getElementById('raw-bay');
const rawToggle = document.getElementById('raw-toggle');
const rawJson = document.getElementById('raw-json');
const emptyState = document.getElementById('empty-state');

// State
let isSearching = false;
let lastData = null;
let selectedStage = null;

// ---------------------------------------------------------------------
// Pipeline stage definitions — the signature "trace" element.
// Each stage reads its own metric + pass/warn/fail status straight off
// the API response, so the trace always reflects what actually happened,
// never a canned animation.
// ---------------------------------------------------------------------
const STAGES = [
    {
        id: 'preprocess', label: 'Preprocess',
        metric: (d) => d.preprocessed && d.preprocessed !== d.query ? 'normalized' : 'unchanged',
        status: () => 'pass',
        facts: (d) => [
            ['Raw query', d.query, null],
            ['Normalized', d.preprocessed, null],
        ],
        note: 'Strips punctuation runs, expands contractions, collapses whitespace before anything else touches the query.',
    },
    {
        id: 'classify', label: 'Classify',
        metric: (d) => d.query_type || 'simple',
        status: (d) => d.query_type === 'complex' ? 'warn' : 'pass',
        facts: (d) => [
            ['Query type', (d.query_type || 'simple').toUpperCase(), d.query_type === 'complex' ? 'warn' : 'pass'],
        ],
        note: 'Rule-based only — no LLM. A complexity-signal keyword (compare, versus, also, both…) routes the query to decomposition.',
    },
    {
        id: 'decompose', label: 'Decompose',
        metric: (d) => (d.sub_queries && d.sub_queries.length > 1) ? `${d.sub_queries.length} sub-queries` : 'single query',
        status: (d) => (d.sub_queries && d.sub_queries.length > 1) ? 'warn' : 'pass',
        facts: (d) => (d.sub_queries || []).map((sq, i) => [`Sub-query ${i + 1}`, sq, null]),
        note: 'Complex queries are split on conjunctions/comparators into focused sub-queries, each retrieved independently and merged.',
    },
    {
        id: 'retrieve', label: 'Retrieve',
        metric: (d) => `${d.raw_chunk_count ?? 0} chunks`,
        status: (d) => (d.raw_chunk_count ?? 0) > 0 ? 'pass' : 'fail',
        facts: (d) => [
            ['Candidates fetched', d.raw_chunk_count ?? 0, null],
            ['Target document', d.target_source || 'none (semantic search)', d.target_source ? 'warn' : null],
        ],
        note: 'Hybrid similarity search maximizes recall — filtering for relevance happens later, in validation, not here.',
    },
    {
        id: 'validate', label: 'Validate',
        metric: (d) => `${d.relevant_count ?? 0} relevant`,
        status: (d) => d.conflict_flag ? 'fail' : (d.sufficiency_flag === false ? 'warn' : 'pass'),
        facts: (d) => [
            ['Stage 3 — relevant chunks', d.relevant_count ?? 0, null],
            ['Stage 4 — conflict flag', d.conflict_flag ? 'DETECTED' : 'none', d.conflict_flag ? 'fail' : 'pass'],
            ['Stage 5 — sufficiency flag', d.sufficiency_flag ? 'sufficient' : 'insufficient', d.sufficiency_flag ? 'pass' : 'warn'],
            ['Stage 5 — query coverage', `${((d.query_coverage_score ?? 0) * 100).toFixed(0)}%`, null],
            ['Confidence', `${d.confidence_tier} · ${((d.confidence_score ?? 0) * 100).toFixed(1)}%`,
                d.confidence_tier === 'HIGH' ? 'pass' : d.confidence_tier === 'MEDIUM' ? 'warn' : 'fail'],
            ['Stage 0 — unverifiable evidence discarded', d.unverified_count ?? 0, (d.unverified_count ?? 0) > 0 ? 'warn' : 'pass'],
        ],
        note: 'The seven-stage validation pipeline: provenance → normalize → dedup → relevance filter → conflict detection → sufficiency check → structuring. Deterministic throughout — no LLM judgement.',
    },
    {
        id: 'decide', label: 'Decide',
        metric: (d) => (d.decision || 'abstain').toUpperCase(),
        status: (d) => d.decision === 'proceed' ? 'pass' : 'fail',
        facts: (d) => [
            ['Decision', (d.decision || 'abstain').toUpperCase(), d.decision === 'proceed' ? 'pass' : 'fail'],
            ['Abstention reason', d.abstention_reason || 'n/a (proceeded)', d.abstention_reason ? 'warn' : null],
        ],
        note: 'Deterministic routing: a conflict retries retrieval once with wider recall; insufficient evidence abstains; otherwise the pipeline proceeds to synthesis.',
    },
    {
        id: 'synthesize', label: 'Synthesize',
        metric: (d) => d.decision === 'proceed'
            ? (d.faithfulness_score != null ? `faithfulness ${(d.faithfulness_score * 100).toFixed(0)}%` : 'synthesized')
            : 'skipped',
        status: (d) => d.decision !== 'proceed' ? 'warn'
            : (d.faithfulness_score == null || d.faithfulness_score >= 0.9) ? 'pass' : 'warn',
        facts: (d) => [
            ['Status', d.decision === 'proceed' ? 'synthesized from validated evidence' : 'skipped — no synthesis without a proceed decision', null],
            ['Faithfulness score', d.faithfulness_score != null ? `${(d.faithfulness_score * 100).toFixed(1)}%` : 'n/a', null],
            ['Unsupported sentences', (d.unsupported_sentences || []).length, (d.unsupported_sentences || []).length > 0 ? 'warn' : 'pass'],
        ],
        note: 'The LLM only ever synthesizes prose from evidence that already passed validation — it never decides what counts as evidence.',
    },
];

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------
async function init() {
    renderTraceSkeleton();
    await updateStats();

    queryBtn.addEventListener('click', handleQuery);
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleQuery();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) uploadFile(e.target.files[0]);
    });

    resetBtn.addEventListener('click', async () => {
        if (confirm('Reset the index? This deletes all indexed documents.')) {
            await resetIndex();
        }
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('active');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('active'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('active');
        if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
    });

    rawToggle.addEventListener('click', () => {
        const open = rawJson.hasAttribute('hidden');
        rawJson.toggleAttribute('hidden', !open);
        rawToggle.classList.toggle('open', open);
    });
}

// ---------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------
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
    const badge = document.getElementById('api-status-badge');
    if (online) {
        badge.className = 'api-status-badge online';
        badge.innerHTML = '<span class="pulse-dot"></span>API online';
    } else {
        badge.className = 'api-status-badge offline';
        badge.innerHTML = '<span class="pulse-dot"></span>API offline — start api.py';
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
    const listEl = document.getElementById('document-list');
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
        chunks.textContent = doc.chunks ? `${doc.chunks}` : '';
        li.appendChild(name);
        li.appendChild(chunks);
        listEl.appendChild(li);
    });
}

async function handleQuery() {
    const query = queryInput.value.trim();
    if (!query || isSearching) return;

    setLoading(true);
    emptyState.setAttribute('hidden', '');
    animateTraceRunning();

    try {
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, k: 5 })
        });
        const data = await response.json();
        if (!response.ok) {
            const detail = data.detail || `HTTP ${response.status}`;
            showNotification(`Search error: ${detail}`, 'error');
            traceState.textContent = 'error';
            traceState.className = 'trace-state';
            return;
        }
        lastData = data;
        renderAll(data);
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

    const indexingNote = showNotification(
        `Indexing ${file.name} — this may take up to a minute…`, 'info', 0
    );
    dropZone.style.pointerEvents = 'none';
    dropZone.style.opacity = '0.5';

    try {
        const response = await fetch(`${API_BASE_URL}/upload`, { method: 'POST', body: formData });
        const data = await response.json();
        if (response.ok) {
            const chunkInfo = data.num_chunks ? ` (${data.num_chunks} chunks indexed)` : '';
            showNotification(`${file.name} uploaded successfully${chunkInfo}`, 'success');
        } else {
            showNotification(`Upload failed: ${data.detail || 'Unknown error'}`, 'error');
        }
        await updateStats();
    } catch (error) {
        showNotification('Upload failed — is the API server running?', 'error');
        console.error('Upload error:', error);
    } finally {
        if (indexingNote && indexingNote.parentNode) indexingNote.remove();
        dropZone.style.pointerEvents = '';
        dropZone.style.opacity = '';
        fileInput.value = '';
    }
}

async function resetIndex() {
    try {
        const response = await fetch(`${API_BASE_URL}/reset`, { method: 'DELETE' });
        const data = await response.json();
        showNotification(data.message, 'success');
        await updateStats();
        lastData = null;
        outcomeBay.setAttribute('hidden', '');
        evidenceBay.setAttribute('hidden', '');
        rawBay.setAttribute('hidden', '');
        traceDetail.setAttribute('hidden', '');
        emptyState.removeAttribute('hidden');
        renderTraceSkeleton();
    } catch (error) {
        showNotification('Reset failed', 'error');
    }
}

// ---------------------------------------------------------------------
// Trace rendering
// ---------------------------------------------------------------------
function renderTraceSkeleton() {
    traceNodes.innerHTML = '';
    STAGES.forEach((stage, i) => {
        if (i > 0) {
            const connector = document.createElement('div');
            connector.className = 'trace-node-connector';
            traceNodes.appendChild(connector);
        }
        const li = document.createElement('li');
        li.className = 'trace-node';
        const btn = document.createElement('button');
        btn.className = 'trace-node-btn status-pending';
        btn.dataset.stageId = stage.id;
        btn.innerHTML = `
            <span class="trace-node-index">0${i + 1}</span>
            <span class="trace-node-label">${stage.label}</span>
            <span class="trace-node-metric">awaiting query</span>
        `;
        btn.addEventListener('click', () => selectStage(stage.id));
        li.appendChild(btn);
        traceNodes.appendChild(li);
    });
    traceState.textContent = 'idle';
    traceState.className = 'trace-state';
}

function animateTraceRunning() {
    traceState.textContent = 'running';
    traceState.className = 'trace-state running';
    document.querySelectorAll('.trace-node-btn').forEach(btn => {
        btn.className = 'trace-node-btn status-active';
        btn.querySelector('.trace-node-metric').textContent = 'processing…';
    });
    document.querySelectorAll('.trace-node-connector').forEach(c => c.classList.remove('lit'));
}

function renderTrace(data) {
    traceState.textContent = 'complete';
    traceState.className = 'trace-state done';

    STAGES.forEach((stage, i) => {
        const btn = traceNodes.querySelector(`[data-stage-id="${stage.id}"]`);
        if (!btn) return;
        const status = stage.status(data);
        btn.className = `trace-node-btn status-${status}`;
        btn.querySelector('.trace-node-metric').textContent = stage.metric(data);
    });
    document.querySelectorAll('.trace-node-connector').forEach(c => c.classList.add('lit'));

    selectStage(selectedStage || 'validate');
}

function selectStage(stageId) {
    selectedStage = stageId;
    document.querySelectorAll('.trace-node-btn').forEach(b => b.classList.toggle('selected', b.dataset.stageId === stageId));

    if (!lastData) return;
    const stage = STAGES.find(s => s.id === stageId);
    if (!stage) return;

    const facts = stage.facts(lastData);
    let html = `<div class="trace-detail-title">${stage.label} — stage detail</div><div class="trace-detail-grid">`;
    if (facts.length === 0) {
        html += `<div class="trace-detail-note">No sub-queries were needed — the query was routed straight through as a single unit.</div>`;
    } else {
        facts.forEach(([k, v, tone]) => {
            html += `<div class="trace-fact"><span class="trace-fact-k">${escapeHtml(String(k))}</span><span class="trace-fact-v${tone ? ' tone-' + tone : ''}">${escapeHtml(String(v))}</span></div>`;
        });
    }
    if (stage.note) {
        html += `<div class="trace-detail-note">${escapeHtml(stage.note)}</div>`;
    }
    html += `</div>`;
    traceDetail.innerHTML = html;
    traceDetail.removeAttribute('hidden');
}

// ---------------------------------------------------------------------
// Outcome + evidence + raw rendering
// ---------------------------------------------------------------------
function renderAll(data) {
    renderTrace(data);
    renderOutcome(data);
    renderEvidence(data);
    renderRaw(data);
}

function renderOutcome(data) {
    const isProceed = data.decision === 'proceed';
    const tier = (data.confidence_tier || 'LOW').toLowerCase();
    const pct = Math.round((data.confidence_score || 0) * 100);

    let html = `
    <div class="outcome-head">
        <div class="outcome-title">
            <h2>Decision</h2>
            <span class="status-pill ${isProceed ? 'proceed' : 'abstain'}">${isProceed ? 'Proceed' : 'Abstain'}</span>
        </div>
        <div class="confidence-meter">
            <span class="confidence-meter-label">Confidence</span>
            <div class="confidence-meter-track"><div class="confidence-meter-fill tier-${tier}" style="width:${pct}%"></div></div>
            <span class="confidence-meter-value">${data.confidence_tier} · ${pct}%</span>
        </div>
    </div>
    <div class="outcome-body">
        <div class="answer-text"></div>
    `;

    if (!isProceed && data.abstention_reason) {
        html += `<div class="faithfulness-row">Reason for abstention: <strong style="color:var(--coral)">${escapeHtml(data.abstention_reason)}</strong></div>`;
    }

    if (isProceed && data.faithfulness_score != null) {
        html += `<div class="faithfulness-row">Faithfulness to evidence: ${(data.faithfulness_score * 100).toFixed(1)}%</div>`;
    }

    if (isProceed && data.unsupported_sentences && data.unsupported_sentences.length > 0) {
        html += `<ul class="unsupported-list">` +
            data.unsupported_sentences.map(s => `<li>Unsupported by evidence: "${escapeHtml(s)}"</li>`).join('') +
            `</ul>`;
    }

    if (data.abstention_reason === 'conflict' && data.conflict_detail && data.conflict_detail.chunks) {
        html += `<div class="conflict-panel"><div class="conflict-panel-title">Conflicting evidence pair</div><div class="conflict-pair">`;
        data.conflict_detail.chunks.forEach(c => {
            html += `<div class="conflict-chunk"><span class="conflict-chunk-source">${escapeHtml(c.source || 'unknown')}</span><span class="conflict-chunk-text"></span></div>`;
        });
        html += `</div></div>`;
    }

    html += `</div>`;

    outcomeBay.innerHTML = html;
    outcomeBay.className = `outcome-bay status-${isProceed ? 'proceed' : 'abstain'}`;
    outcomeBay.removeAttribute('hidden');

    // set text content safely (avoid HTML injection from model/document text)
    outcomeBay.querySelector('.answer-text').textContent = data.answer || '(no answer)';
    if (data.abstention_reason === 'conflict' && data.conflict_detail && data.conflict_detail.chunks) {
        const nodes = outcomeBay.querySelectorAll('.conflict-chunk-text');
        data.conflict_detail.chunks.forEach((c, i) => { if (nodes[i]) nodes[i].textContent = c.text || ''; });
    }
}

function renderEvidence(data) {
    const chunks = data.chunks || [];
    const similarity = data.similarity_scores || [];
    const raw = data.raw_scores || [];

    let html = '';

    html += `<div class="evidence-group open" id="group-accepted">
        <div class="evidence-group-head" data-group="group-accepted">
            <h3>Accepted evidence <span class="evidence-count">${chunks.length} chunk${chunks.length === 1 ? '' : 's'}</span></h3>
            <span class="evidence-group-chevron">&rsaquo;</span>
        </div>
        <div class="evidence-group-body" id="accepted-body"></div>
    </div>`;

    const unverifiedCount = data.unverified_count || 0;
    html += `<div class="evidence-group" id="group-rejected">
        <div class="evidence-group-head" data-group="group-rejected">
            <h3>Filtered out <span class="evidence-count">${unverifiedCount} unverifiable</span></h3>
            <span class="evidence-group-chevron">&rsaquo;</span>
        </div>
        <div class="evidence-group-body" id="rejected-body"></div>
    </div>`;

    evidenceBay.innerHTML = html;
    evidenceBay.removeAttribute('hidden');

    const acceptedBody = document.getElementById('accepted-body');
    if (chunks.length === 0) {
        acceptedBody.innerHTML = '<div class="unverified-note">No evidence cleared validation for this query.</div>';
    } else {
        chunks.forEach((chunk, i) => {
            const card = document.createElement('div');
            card.className = 'evidence-card';
            const sim = (similarity[i] * 100).toFixed(1);
            const rw = raw[i] != null ? (raw[i] * 100).toFixed(1) : null;
            card.innerHTML = `
                <div class="evidence-card-head">
                    <span class="evidence-source"><span class="evidence-rank-badge">#${chunk.rank ?? i + 1}</span> ${escapeHtml(chunk.source_document || 'unknown')} <span class="evidence-section">/ ${escapeHtml(chunk.section || '')}</span></span>
                    <span class="evidence-scores">score ${sim}% ${rw ? `<span class="raw">raw ${rw}%</span>` : ''}</span>
                </div>
                <div class="evidence-text"></div>
            `;
            card.querySelector('.evidence-text').textContent = chunk.text || '';
            acceptedBody.appendChild(card);
        });
    }

    const rejectedBody = document.getElementById('rejected-body');
    if (unverifiedCount > 0) {
        rejectedBody.innerHTML = `<div class="unverified-note">
            <strong>${unverifiedCount}</strong> retrieved chunk${unverifiedCount === 1 ? '' : 's'} could not be traced back to the ingested corpus
            (provenance check, Stage 0) and were discarded before relevance filtering ever ran.
            Source${(data.unverified_sources || []).length === 1 ? '' : 's'} involved:
            ${(data.unverified_sources || []).map(s => escapeHtml(s)).join(', ') || 'n/a'}.
        </div>`;
    } else {
        rejectedBody.innerHTML = '<div class="unverified-note">Nothing was discarded at the provenance stage for this query.</div>';
    }

    evidenceBay.querySelectorAll('.evidence-group-head').forEach(head => {
        head.addEventListener('click', () => {
            document.getElementById(head.dataset.group).classList.toggle('open');
        });
    });
}

function renderRaw(data) {
    rawJson.textContent = JSON.stringify(data, null, 2);
    rawBay.removeAttribute('hidden');
}

// ---------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------
function setLoading(isLoading) {
    isSearching = isLoading;
    queryBtn.disabled = isLoading;
    queryBtn.innerHTML = isLoading ? '<span>Tracing…</span>' : '<span>Run query</span>';
    queryInput.disabled = isLoading;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
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
    return note;
}

// Start app
init();
