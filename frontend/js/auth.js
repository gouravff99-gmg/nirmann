// =============================================
//  NIRMAN — Authentication
//  File: frontend/js/auth.js
// =============================================

function showLoginModal() {
  document.getElementById('login-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('login-email')?.focus(), 100);
}

function hideLoginModal() {
  document.getElementById('login-modal').classList.add('hidden');
  document.getElementById('login-modal-error').style.display = 'none';
}

/* ───── LOGIN FORM ───── */

async function doLogin() {
  const email    = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl    = document.getElementById('login-modal-error');
  const btn      = document.getElementById('login-btn');

  errEl.style.display = 'none';
  btn.disabled = true;
  btn.textContent = '⏳ Signing in...';

  try {
    const d = await api('POST', '/auth/login', { email, password });
    handleLogin(d.token, d.user);
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}

/* ───── QUICK LOGIN (landing page buttons) ───── */

async function quickLogin(email) {
  const errEl = document.getElementById('landing-login-error');
  if (errEl) errEl.style.display = 'none';
  try {
    const d = await api('POST', '/auth/login', { email, password: NIRMAN_CONFIG.DEMO_PASSWORD });
    handleLogin(d.token, d.user);
  } catch (e) {
    toast(e.message, 'error');
    const el = document.getElementById('landing-login-error');
    if (el) { el.textContent = e.message; el.style.display = 'block'; }
  }
}

/* ───── HANDLE SUCCESSFUL LOGIN ───── */

function handleLogin(tok, usr) {
  nirmanState.token = tok;
  nirmanState.user  = usr;
  localStorage.setItem('nirman_token', tok);
  localStorage.setItem('nirman_user', JSON.stringify(usr));
  hideLoginModal();
  showApp();
}

/* ───── LOGOUT ───── */

function logout() {
  localStorage.removeItem('nirman_token');
  localStorage.removeItem('nirman_user');
  nirmanState.token = null;
  nirmanState.user  = null;
  nirmanState.pageHistory = [];

  document.getElementById('app').classList.add('hidden');
  document.getElementById('landing').classList.remove('hidden');
  document.getElementById('chat-widget').classList.add('hidden');
  document.getElementById('login-email').value = '';
  document.getElementById('login-password').value = '';
}
