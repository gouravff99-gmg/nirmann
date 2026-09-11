// =============================================
//  NIRMAN — Application State & Navigation
//  File: frontend/js/app.js
// =============================================

/* ───── GLOBAL STATE ───── */

const nirmanState = {
  token: localStorage.getItem('nirman_token') || null,
  user:  null,
  currentPage: '',
  pageHistory: [],   // for back-button tracking
};

// Restore user from localStorage
try {
  nirmanState.user = JSON.parse(localStorage.getItem('nirman_user') || 'null');
} catch (e) {
  nirmanState.user = null;
}

/* ───── NAVIGATION ───── */

/**
 * Navigate to a page.
 * @param {string} page        Page key (must exist in PAGES registry)
 * @param {object} [params]    Optional params passed to the page function
 * @param {boolean} [addToHistory] Whether to push to pageHistory (default true)
 */
function navigate(page, params = {}, addToHistory = true) {
  if (addToHistory && nirmanState.currentPage && nirmanState.currentPage !== page) {
    nirmanState.pageHistory.push({ page: nirmanState.currentPage, params: window._pageParams || {} });
    if (nirmanState.pageHistory.length > 20) nirmanState.pageHistory.shift(); // cap history
  }
  window._pageParams = params;
  nirmanState.currentPage = page;

  // Update sidebar active state
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const navEl = document.getElementById('nav-' + page);
  if (navEl) navEl.classList.add('active');

  window.scrollTo({ top: 0, behavior: 'smooth' });
  showLoading();

  if (PAGES[page]) {
    PAGES[page](params);
  } else {
    document.getElementById('page-content').innerHTML = `
      <div class="card" style="text-align:center;padding:60px">
        <div style="font-size:48px;margin-bottom:16px">🔍</div>
        <div style="font-size:17px;font-weight:700;margin-bottom:8px">Page Not Found</div>
        <p style="color:var(--slate)">The page "<code>${page}</code>" doesn't exist.</p>
        <button class="btn btn-primary mt-3" onclick="navigate('dashboard')">← Dashboard</button>
      </div>`;
  }
}

/**
 * Go back to the previous page in history.
 * Falls back to the role's default page.
 */
function goBack() {
  if (nirmanState.pageHistory.length > 0) {
    const prev = nirmanState.pageHistory.pop();
    navigate(prev.page, prev.params, false);
  } else {
    const defaultPage = NIRMAN_CONFIG.DEFAULT_PAGE[nirmanState.user?.role] || 'dashboard';
    navigate(defaultPage, {}, false);
  }
}

/* ───── APP SHELL ───── */

/**
 * Show the main app shell after login. Renders sidebar and navigates to default page.
 */
function showApp() {
  document.getElementById('landing').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  document.getElementById('chat-widget').classList.remove('hidden');

  const u = nirmanState.user;
  document.getElementById('user-name-display').textContent = u.name;
  document.getElementById('role-badge').textContent = u.role;

  // Build sidebar nav
  const navItems = NIRMAN_CONFIG.NAV[u.role] || NIRMAN_CONFIG.NAV.APPLICANT;
  document.getElementById('sidebar-nav').innerHTML = navItems.map(it =>
    `<button class="nav-item" id="nav-${it.page}" onclick="navigate('${it.page}')">
       <span>${it.icon}</span> ${it.label}
     </button>`
  ).join('');

  // Clear history and navigate to default
  nirmanState.pageHistory = [];
  navigate(NIRMAN_CONFIG.DEFAULT_PAGE[u.role] || 'dashboard', {}, false);
}

/* ───── MODALS ───── */

function openModal(size) {
  const box = document.getElementById('generic-modal-box');
  if (size === 'lg') box.className = 'modal-box modal-box-lg';
  else if (size === 'sm') box.className = 'modal-box modal-box-sm';
  else box.className = 'modal-box';
  document.getElementById('generic-modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('generic-modal').classList.add('hidden');
}

function openCertModal() {
  document.getElementById('cert-modal').classList.remove('hidden');
}

function closeCertModal() {
  document.getElementById('cert-modal').classList.add('hidden');
}

/* ───── CLICK-OUTSIDE TO CLOSE ───── */
document.getElementById('login-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) hideLoginModal();
});
document.getElementById('generic-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});
document.getElementById('cert-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeCertModal();
});

/* ───── PAGES REGISTRY ───── */
// Each page module registers itself here.
const PAGES = {};
