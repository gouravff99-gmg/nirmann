// =============================================
//  NIRMAN — Utilities (API, Toast, Badge, etc.)
//  File: frontend/js/utils.js
// =============================================

/* ───── API HELPER ───── */

/**
 * Clear a stale/invalid session (used on 401). Removes the stored token,
 * hides the app shell and returns the user to the landing/login screen.
 */
function clearStaleSession() {
  localStorage.removeItem('nirman_token');
  localStorage.removeItem('nirman_user');
  nirmanState.token = null;
  nirmanState.user  = null;
  nirmanState.pageHistory = [];
  const app = document.getElementById('app');
  const landing = document.getElementById('landing');
  const chat = document.getElementById('chat-widget');
  if (app) app.classList.add('hidden');
  if (chat) chat.classList.add('hidden');
  if (landing) landing.classList.remove('hidden');
}

/**
 * Make an authenticated JSON request to the NIRMAN API.
 * @param {string} method  HTTP verb
 * @param {string} path    API path (e.g. '/businesses/')
 * @param {object} [body]  JSON body (for POST/PUT)
 * @returns {Promise<object>}
 */
async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (nirmanState.token) opts.headers['Authorization'] = 'Bearer ' + nirmanState.token;
  if (body) opts.body = JSON.stringify(body);

  let response;
  try {
    response = await fetch(NIRMAN_CONFIG.API_BASE + path, opts);
  } catch (e) {
    throw new Error('Cannot connect to NIRMAN server. Is the backend running on port 5001?');
  }

  // Parse the body safely — the API is JSON, but proxies/debuggers can
  // occasionally return HTML error pages.
  let data = {};
  const text = await response.text();
  try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }

  if (response.status === 401) {
    // Session is invalid or stale (e.g. token minted before a DB reseed).
    clearStaleSession();
    toast('Session expired — please log in again.', 'warning');
    throw new Error(data.error || data.msg || 'Session expired — please log in again.');
  }

  if (!response.ok) {
    throw new Error(data.error || data.msg || `Request failed (${response.status})`);
  }
  return data;
}

/**
 * Upload a file via multipart/form-data.
 */
async function apiUpload(path, formData) {
  const response = await fetch(NIRMAN_CONFIG.API_BASE + path, {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + nirmanState.token },
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Upload failed');
  return data;
}

/* ───── TOAST NOTIFICATIONS ───── */

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'info'|'success'|'error'|'warning'} [type]
 */
function toast(message, type = 'info') {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `${icons[type] || 'ℹ️'} <span>${message}</span>`;
  document.getElementById('toasts').appendChild(el);
  // Fade out and remove
  setTimeout(() => { el.style.opacity = '0'; }, 4500);
  setTimeout(() => el.remove(), 5000);
}

/* ───── STATUS BADGE ───── */

const STATUS_LABELS = {
  DRAFT:                ['badge-slate',  'Draft'],
  SUBMITTED:            ['badge-blue',   'Submitted'],
  UNDER_REVIEW:         ['badge-blue',   'Under Review'],
  CORRECTION_REQUIRED:  ['badge-amber',  'Correction Required'],
  INSPECTION_REQUIRED:  ['badge-amber',  'Inspection Required'],
  INSPECTION_SCHEDULED: ['badge-purple', 'Inspection Scheduled'],
  INSPECTION_COMPLETED: ['badge-cyan',   'Inspection Completed'],
  DECISION_PENDING:     ['badge-amber',  'Decision Pending'],
  APPROVED:             ['badge-green',  '✓ Approved'],
  REJECTED:             ['badge-red',    '✗ Rejected'],
  NOT_APPLIED:          ['badge-slate',  'Not Applied'],
  EXPIRED:              ['badge-slate',  'Expired'],
  OPEN:                 ['badge-slate',  'Open'],
  RESOLVED:             ['badge-green',  'Resolved'],
  UNDER_REVIEW_G:       ['badge-blue',   'Under Review'],
};

/**
 * Return an HTML badge string for a given status.
 */
function badge(status) {
  const [cls, label] = STATUS_LABELS[status] || ['badge-slate', status || 'Unknown'];
  return `<span class="badge ${cls}">${label}</span>`;
}

/* ───── DATE FORMATTERS ───── */

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function fmtDateTime(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
}

/* ───── SECTOR ICON ───── */

function sectorIcon(sector) {
  const map = {
    FOOD_PROCESSING: '🥦', FOOD_SERVICE: '🥗', MANUFACTURING: '⚙️',
    RESTAURANT: '🍽️', CONSTRUCTION: '🏗️', ELECTRONICS: '💡',
    REAL_ESTATE: '🏢', RETAIL: '🛒', HEALTHCARE: '🏥',
    EDUCATION: '📚', WHOLESALE: '📦', SERVICE: '🔧',
  };
  return map[sector] || '🏢';
}

/* ───── SHOW FULL-PAGE ERROR ───── */

function showError(msg) {
  document.getElementById('page-content').innerHTML = `
    <div class="danger-box" style="text-align:center;padding:40px">
      <div style="font-size:36px;margin-bottom:12px">❌</div>
      <div style="font-weight:700;font-size:16px;margin-bottom:8px">Something went wrong</div>
      <div style="font-size:14px;margin-bottom:20px">${msg}</div>
      <button class="btn btn-outline btn-sm" onclick="navigate(nirmanState.user?.role ? NIRMAN_CONFIG.DEFAULT_PAGE[nirmanState.user.role] : 'dashboard')">
        ← Go to Dashboard
      </button>
    </div>`;
}

/* ───── LOADING STATE ───── */
function showLoading() {
  document.getElementById('page-content').innerHTML = `
    <div style="display:flex;align-items:center;justify-content:center;height:200px;color:var(--slate);gap:12px;font-size:14px">
      <span class="spin">⏳</span> Loading...
    </div>`;
}
