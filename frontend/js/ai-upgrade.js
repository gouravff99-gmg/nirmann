/*
 * NIRMAN SIH AI workflow upgrade
 * This is deliberately an extension of the existing SPA: it reuses its API,
 * shell, modal and authentication helpers rather than introducing a second UI.
 */
(function () {
  const AI_NAV = {
    APPLICANT: [
      ['dashboard', '🏠', 'Unified Dashboard'], ['demo-workflows', '✨', 'Explore AI Workflows'],
      ['businesses', '🏢', 'My Businesses'], ['applications', '📋', 'Applications'],
      ['certificates', '🏅', 'Licenses & Renewals'], ['notifications', '🔔', 'Notifications'],
      ['schemes', '🛡️', 'AI-Matched Schemes'], ['licence-knowledge', '📚', 'Licence Knowledge'],
      ['grievances', '📩', 'Grievances'],
    ],
    AI_AGENT: [
      ['ai-dashboard', '🤖', 'AI Command Center'], ['ai-queue', '📥', 'Decision Queue'],
      ['demo-workflows', '✨', 'Five Demo Workflows'],
      ['ai-audit', '🧾', 'AI Audit Trail'], ['notifications', '🔔', 'System Alerts'],
    ],
    OFFICER: [
      ['officer-dashboard', '🏛️', 'Licence Officer / Inspector'],
      ['officer-inbox', '📥', 'Applications Inbox'],
      ['inspector-dashboard', '🔍', 'Inspection Tasks'],
      ['notifications', '🔔', 'Notifications'],
    ],
    ADMIN: [
      ['admin-dashboard', '⚙️', 'Governance Dashboard'], ['demo-workflows', '✨', 'Five Demo Workflows'],
      ['admin-applications', '📋', 'All Applications'], ['admin-users', '👥', 'Users'],
      ['ai-audit', '🧾', 'AI Audit Trail'], ['notifications', '🔔', 'Notifications'],
    ],
  };

  const primaryPage = { APPLICANT: 'dashboard', AI_AGENT: 'ai-dashboard', ADMIN: 'admin-dashboard', OFFICER: 'officer-dashboard' };
  const statusClass = {
    APPROVED: 'badge-green', APPROVAL_READY: 'badge-green', VERIFIED: 'badge-green',
    PARALLEL_PROCESSING: 'badge-purple', AI_REVIEW: 'badge-purple', AI_ANALYSIS: 'badge-purple',
    AI_PROCESSING: 'badge-purple', AI_CHECK_COMPLETE: 'badge-purple',
    SUBMITTED_TO_AUTHORITY: 'badge-blue', ASSIGNED_TO_OFFICER: 'badge-blue',
    INSPECTION_SCHEDULED: 'badge-purple', INSPECTION_COMPLETED: 'badge-cyan', INSPECTION_PASSED: 'badge-green',
    CORRECTION_REQUIRED: 'badge-amber', NEEDS_CORRECTION: 'badge-amber',
    ADDITIONAL_DOCUMENTS_REQUIRED: 'badge-amber',
    INSPECTION_REQUIRED: 'badge-amber', EXCEPTION: 'badge-red', REJECTED: 'badge-red',
    RESUBMISSION_REQUIRED: 'badge-red',
    UNDER_REVIEW: 'badge-blue', SUBMITTED: 'badge-blue', DOCUMENT_VALIDATION: 'badge-blue',
    UNDER_OFFICER_REVIEW: 'badge-blue',
    VALIDATION_PENDING: 'badge-amber',
    UPLOADED: 'badge-blue', NOT_UPLOADED: 'badge-slate',
    DRAFT: 'badge-slate',
  };

  function safe(text) {
    return String(text === undefined || text === null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }
  function readable(value) { return safe(String(value || '—').replace(/_/g, ' ')); }
  function stateBadge(state) { return `<span class="badge ${statusClass[state] || 'badge-slate'}">${readable(state)}</span>`; }
  function riskBadge(level) { return `<span class="badge ${level === 'LOW' ? 'badge-green' : level === 'HIGH' ? 'badge-red' : 'badge-amber'}">${safe(level)} RISK</span>`; }
  function actorTag(name) {
    const n = String(name || '').trim().toLowerCase();
    if (/arjun/.test(n)) return '<span class="badge badge-blue">LICENCE OFFICER / INSPECTOR</span>';
    if (/ai |ai$|agent/.test(n) || n === 'ai compliance agent') return '<span class="badge badge-purple">AI COMPLIANCE AGENT</span>';
    if (/admin/.test(n)) return '<span class="badge badge-slate">ADMIN</span>';
    return '<span class="badge badge-slate">APPLICANT</span>';
  }
  function currentUser() { return user || null; }
  function isAdmin() { return currentUser()?.role === 'ADMIN'; }
  function demoNotice(compact) {
    return `<div class="${compact ? 'text-xs' : 'warning-box mb-4'}" style="${compact ? 'color:#92400e' : ''}">⚠️ <strong>DEMO ENVIRONMENT</strong> — AI analysis, regulatory rules, documents, schemes and certificates are simulated for demonstration. NIRMAN does not issue legally valid government approvals.</div>`;
  }
  function showLoadingUpgrade() {
    document.getElementById('page-content').innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:220px;color:var(--slate)">✨ Loading simulated AI workflow…</div>';
  }

  /* The system-role entry point is separate from human authentication. */
  window.openAiAgentDemo = async function () {
    try {
      const response = await fetch(API + '/ai-agent/demo-session', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Unable to enter the AI demo.');
      handleLogin(payload.token, payload.user);
      toast('AI DEMO mode entered — simulated system role.', 'info');
    } catch (error) { toast(error.message, 'error'); }
  };

  /* Licence Officer / Inspector demo entry — the single operational officer
     account (Arjun Singh, inspector@demo.com). Covers application review,
     inspection and final approval. Licence desks are filters, not accounts. */
  window.openLicenceOfficerDemo = async function () {
    try {
      const response = await fetch(API + '/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'inspector@demo.com', password: 'Demo@1234' }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Unable to open the Licence Officer demo.');
      handleLogin(payload.token, payload.user);
      toast('LICENCE OFFICER / INSPECTOR demo entered — Arjun Singh. Covers review, inspection and final approval.', 'info');
    } catch (error) { toast(error.message, 'error'); }
  };

  window.showApp = function () {
    if (!user) return;
    const isSystemRole = user.role === 'AI_AGENT' || user.role === 'OFFICER';
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    document.getElementById('chat-widget').classList.toggle('hidden', isSystemRole);
    document.getElementById('user-name-display').textContent = user.name;
    document.getElementById('role-badge').textContent =
      user.role === 'AI_AGENT' ? 'SYSTEM ROLE · AI DEMO'
      : user.role === 'OFFICER' ? 'LICENCE OFFICER / INSPECTOR · DEMO'
      : user.role;
    const items = AI_NAV[user.role] || AI_NAV.APPLICANT;
    document.getElementById('sidebar-nav').innerHTML = items.map(([page, icon, label]) =>
      `<button class="nav-item" id="nav-${page}" onclick="navigate('${page}')"><span>${icon}</span> ${label}</button>`
    ).join('');
    navigate(primaryPage[user.role] || 'dashboard');
  };

  function card(workflow) {
    const b = workflow;
    return `<button class="demo-btn" onclick="navigate('ai-workflow',{businessId:'${b.id}'})" style="min-height:215px">
      <div class="flex justify-between items-start"><span style="font-size:31px">${b.icon}</span>${riskBadge(b.risk)}</div>
      <div style="font-size:15px;font-weight:800;margin-top:12px">${safe(b.name)}</div>
      <div class="text-xs text-muted mt-1">${safe(b.type)}</div>
      <div class="flex justify-between text-xs mt-3"><span>${b.requirements} requirements</span><span>${safe(b.inspection_status)}</span></div>
      <div class="progress-track mt-2"><div class="progress-fill" style="width:${b.progress}%"></div></div>
      <div class="flex justify-between text-xs mt-2"><span>${b.progress}% complete</span>${stateBadge(b.state)}</div>
    </button>`;
  }

  async function workflows() { return (await api('GET', '/ai-agent/demo-workflows')).businesses || []; }

  function reqDot(state) { return state === 'APPROVED' ? '#16a34a' : (state === 'NOT_APPLIED' || !state ? '#cbd5e1' : '#d97706'); }

  /* Icon for a business sector — mirrored from the global sectorIcon helper so
     the applicant dashboard never depends on the demo-workflows payload. */
  function sectorIconSafe(sector) {
    const icons = { FOOD_PROCESSING:'🥦', MANUFACTURING:'⚙️', RESTAURANT:'🍽️', CONSTRUCTION:'🏗️', ELECTRONICS:'💡', REAL_ESTATE:'🏢', RETAIL:'🛒', HEALTHCARE:'🏥', EDUCATION:'📚', SERVICE:'🛠️' };
    return icons[(sector || '').toString().toUpperCase()] || '🏢';
  }

  /* Single source of truth for "how many applications does each business need".
     Backed by the same compliance engine the Inspector and Admin dashboards
     rely on — nothing here is hardcoded. */
  async function requirementsSection() {
    const payload = await api('GET', '/businesses/');
    const list = (payload.businesses || []);
    if (!list.length) return '';
    const total = list.reduce((n, b) => n + (b.total_required || 0), 0);
    const done = list.reduce((n, b) => n + (b.required_approvals || []).filter(r => r.application_status === 'APPROVED').length, 0);
    return `
      <div class="card mb-4">
        <div class="flex justify-between items-center gap-2 flex-wrap mb-3">
          <div>
            <div style="font-weight:800;font-size:16px">Required applications — calculated for you</div>
            <div class="text-xs text-muted mt-1">Each approval below is computed live from NIRMAN's compliance rules and the business's actual application status. A restaurant, a factory and a pharmacy each get a different set.</div>
          </div>
          <button class="btn btn-outline btn-sm" onclick="navigate('businesses')">My businesses →</button>
        </div>
        <div style="display:flex;align-items:baseline;gap:12px;background:linear-gradient(110deg,#eef2ff,#dbeafe);border:1px solid #c7d2fe;border-radius:12px;padding:14px 18px;margin-bottom:14px;flex-wrap:wrap">
          <span style="font-size:34px;font-weight:900;color:#4338ca">${total}</span>
          <span class="text-sm" style="color:#1e3a8a;font-weight:700">total applications required</span>
          <span class="text-xs" style="color:#1e3a8a;opacity:.85">across ${list.length} business${list.length === 1 ? '' : 'es'} · ${done} already approved</span>
        </div>
        ${list.map(b => {
          const reqs = b.required_approvals || [];
          const bdone = reqs.filter(r => r.application_status === 'APPROVED').length;
          return `
          <div style="border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:12px;background:#fff">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><strong style="font-size:15px">${safe(b.name)}</strong>${stateBadge(b.status)}</div>
              <div style="display:flex;align-items:baseline;gap:8px"><span style="font-size:26px;font-weight:900;color:#4338ca">${b.total_required}</span><span class="text-sm text-muted">applications required</span><span class="text-xs text-muted">(${bdone} approved)</span></div>
            </div>
            <div style="margin-top:10px">${reqs.map(r => `<span title="${safe(r.why_triggered || r.name)}" style="display:inline-block;background:#f8fafc;border:1px solid var(--border);border-radius:999px;padding:4px 11px;font-size:12px;margin:4px 5px 0 0;white-space:nowrap"><span style="color:${reqDot(r.application_status)};font-weight:800">●</span> ${safe(r.name)} <span style="color:${reqDot(r.application_status)};font-weight:600;text-transform:capitalize">${readable(r.application_status)}</span></span>`).join('')}</div>
            <div class="text-xs text-muted mt-2">${b.pending_documents} documents still to apply for ${safe(b.name)}</div>
            <div class="text-xs mt-2"><button class="btn btn-outline btn-sm" onclick="navigate('business-detail',{businessId:'${safe(b.id)}'})">Open business dashboard →</button></div>
          </div>`;
        }).join('')}
      </div>`;
  }

  PAGES['dashboard'] = async function () {
    showLoadingUpgrade();
    try {
      /* Applicant dashboard is built ONLY from the authenticated user's own
         data (the /businesses/ endpoint filters by owner_id). It intentionally
         does NOT call /ai-agent/demo-workflows, so a brand-new applicant never
         inherits demo businesses/applications. */
      const suPayload = await api('GET', '/businesses/').catch(() => ({ businesses: [] }));
      const su = suPayload.businesses || [];
      const reqSection = (await requirementsSection());
      const applicationsInProgress = su.reduce((n, b) => n + (b.pending || 0) + (b.corrections || 0), 0);
      const inspections = su.reduce((n, b) => n + (b.inspections || 0), 0);
      const pendingDocs = su.reduce((n, b) => n + (b.pending_documents || 0), 0);
      const attentionRows = [];
      su.forEach(b => (b.required_approvals || []).forEach(r => { if (r.application_status !== 'APPROVED') attentionRows.push({ business: b.name, app: r, businessId: b.id }); }));
      const emptyState = `
        <div class="card" style="text-align:center;padding:60px 24px;margin-bottom:16px">
          <div style="font-size:48px;margin-bottom:16px">🏢</div>
          <div style="font-size:18px;font-weight:800;margin-bottom:8px">No businesses registered yet</div>
          <p class="text-muted" style="max-width:420px;margin:0 auto 20px">Start your first business application to begin the NIRMAN approval process.</p>
          <button class="btn btn-primary" onclick="navigate('create-business')">+ Register a Business</button>
        </div>`;
      document.getElementById('page-content').innerHTML = `
        <div class="flex justify-between items-start gap-3 flex-wrap mb-4">
          <div><div class="page-title">My Dashboard</div><div class="page-subtitle">Welcome to NIRMAN. Your businesses, applications and what still needs your attention.</div></div>
          <button class="btn btn-primary" onclick="navigate('create-business')">+ Register a business</button>
        </div>
        <div class="grid-4 mb-4">
          ${[['🏢', su.length, 'Businesses'], ['📋', applicationsInProgress, 'Applications in progress'], ['🔍', inspections, 'Inspections'], ['📄', pendingDocs, 'Documents to submit']].map(x=>`<div class="stat-card"><div class="stat-icon" style="background:#eef2ff">${x[0]}</div><div class="stat-value" style="font-size:${String(x[1]).length>4?'18':'28'}px">${x[1]}</div><div class="stat-label">${x[2]}</div></div>`).join('')}
        </div>
        <div class="flex justify-between items-center mb-3"><div><div style="font-size:17px;font-weight:800">My Businesses</div><div class="text-muted text-sm">Live progress across your registered activities.</div></div><button class="btn btn-outline btn-sm" onclick="navigate('businesses')">All businesses →</button></div>
        ${su.length === 0 ? emptyState : `<div class="grid-3 mb-4">${su.map(b=>{
          const total = b.total_required || 0;
          const done = (b.required_approvals || []).filter(r => r.application_status === 'APPROVED').length;
          const pct = total ? Math.round((done / total) * 100) : 0;
          return `
          <div class="card" style="margin:0">
            <div class="flex justify-between items-start"><div class="flex items-center gap-2"><span style="font-size:22px">${sectorIconSafe(b.sector)}</span><strong>${safe(b.name)}</strong></div>${stateBadge(b.status)}</div>
            <div class="text-xs text-muted mt-1">${safe((b.business_type || '').replace(/_/g, ' '))}</div>
            <div class="progress-track mt-3"><div class="progress-fill" style="width:${pct}%"></div></div>
            <div class="flex justify-between text-xs mt-2"><span>${pct}% complete</span><span>${total} requirements</span></div>
            <button class="btn btn-outline btn-sm w-full mt-3" onclick="navigate('business-detail',{businessId:'${b.id}'})">Open dashboard →</button>
          </div>`;}).join('')}</div>`}
        <div class="card mb-4" style="border-left:4px solid #22c55e">
          <div class="flex justify-between items-center gap-2 flex-wrap mb-2">
            <div style="font-weight:800;font-size:16px">Applications still requiring your attention</div>
            <button class="btn btn-outline btn-sm" onclick="navigate('applications')">Review my applications →</button>
          </div>
          <div class="text-xs text-muted mb-3">Only the applications that are not yet approved, listed across your businesses.</div>
          ${attentionRows.length ? '<div style="display:flex;flex-direction:column;gap:8px">' + attentionRows.map(r => `
            <div class="flex justify-between items-center gap-2" style="border:1px solid var(--border);border-radius:10px;padding:10px 13px">
              <div><div style="font-weight:700">${safe(r.app.name)}</div><div class="text-xs text-muted">${safe(r.business)}</div></div>
              <div class="flex items-center gap-2"><span style="color:${reqDot(r.app.application_status)};font-weight:800">●</span><span class="text-xs" style="text-transform:capitalize">${readable(r.app.application_status)}</span><button class="btn btn-outline btn-sm" onclick="navigate('business-detail',{businessId:'${r.businessId}'})">Open</button></div>
            </div>`).join('') + '</div>' : (su.length === 0 ? '<div class="text-muted">No applications yet. Register a business to get started.</div>' : '<div class="success-box">🎉 Everything is approved. No outstanding applications.</div>')}
        </div>
        ${reqSection}`;
    } catch (error) { showError('Failed to load your dashboard: ' + error.message); }
  };

  PAGES['demo-workflows'] = async function () {
    showLoadingUpgrade();
    try {
      const all = await workflows();
      document.getElementById('page-content').innerHTML = `
        <div class="page-title">Explore AI Approval Workflows</div>
        <div class="page-subtitle">Different business activity produces a different checklist, risk score, department route, inspection plan and incentive match.</div>
        ${demoNotice(false)}
        <div class="card mb-4" style="border-left:4px solid #6366f1"><div style="font-weight:800">DEMO REGULATORY RULES</div><div class="text-sm text-muted mt-1">Restaurant has food, fire and pollution-related workflows. IT / Software receives only its low-complexity services route — no unnecessary food, fire or pollution approvals.</div></div>
        <div class="grid-3">${all.map(card).join('')}</div>`;
    } catch (error) { showError('Failed to load workflows: ' + error.message); }
  };

  function timeline(state) {
    const names = ['Submitted','AI Analysis','Checklist','Documents','Departments','Parallel Processing','Inspection','Approval Ready','Approved'];
    const map = { DRAFT:0, SUBMITTED:1, AI_PROCESSING:1, AI_CHECK_COMPLETE:1, AI_ANALYSIS:2, CHECKLIST_GENERATED:3, DOCUMENT_VALIDATION:4, CORRECTION_REQUIRED:4, DEPARTMENT_ROUTING:5, SUBMITTED_TO_AUTHORITY:5, ASSIGNED_TO_OFFICER:5, PARALLEL_PROCESSING:6, INSPECTION_REQUIRED:6, INSPECTION_SCHEDULED:6, INSPECTION_COMPLETED:6, INSPECTION_PASSED:7, AI_REVIEW:7, EXCEPTION:6, APPROVAL_READY:8, DECISION_PENDING:7, APPROVED:9 };
    const complete = map[state] || 1;
    return `<div class="flex" style="overflow-x:auto;padding:4px 0 8px">${names.map((name, index)=>`<div class="flex items-center" style="flex-shrink:0"><div class="step-col"><div class="step-circle ${index < complete ? 'done' : index === complete ? 'active' : ''}">${index < complete ? '✓' : index + 1}</div><div class="step-label ${index <= complete ? 'active' : ''}">${name}</div></div>${index < names.length - 1 ? `<div class="step-line ${index < complete ? 'done' : ''}"></div>` : ''}</div>`).join('')}</div>`;
  }

  function actionButton(w) {
    const id = w.business.id;
    if (w.business.name === 'Urban Spice Restaurant' && w.state === 'CORRECTION_REQUIRED') return `<button class="btn btn-primary" onclick="aiRevalidate('${id}')">✨ Fix document & revalidate</button>`;
    if (w.inspection && ['SCHEDULED','ASSIGNED'].includes(w.inspection.status)) return `<button class="btn btn-primary" onclick="navigate('inspector-dashboard')">🔍 Open inspection task</button>`;
    if (w.state === 'APPROVAL_READY') return isAdmin() ? `<button class="btn btn-success" onclick="aiApprove('${id}')">✓ Accept AI recommendation</button>` : `<span class="text-sm text-muted">Awaiting accountable Admin decision</span>`;
    if (w.state === 'APPROVED') return `<button class="btn btn-success" onclick="navigate('certificates')">🏅 View prototype certificate</button>`;
    return `<button class="btn btn-outline" onclick="navigate('demo-workflows')">Compare another workflow</button>`;
  }

  PAGES['ai-workflow'] = async function (params) {
    const id = params?.businessId || window._pageParams?.businessId;
    if (!id) { navigate('demo-workflows'); return; }
    showLoadingUpgrade();
    try {
      const w = (await api('GET', `/ai-agent/workflow/${id}`)).workflow;
      const done = w.requirements.filter(r => r.status === 'APPROVED').length;
      document.getElementById('page-content').innerHTML = `
        <div class="flex justify-between items-start gap-3 flex-wrap mb-3"><div class="flex gap-3"><button class="btn btn-outline btn-sm btn-icon" onclick="navigate('demo-workflows')">←</button><div><div class="flex items-center gap-2 flex-wrap"><div class="page-title" style="font-size:22px">${w.profile.icon} ${safe(w.business.name)}</div>${riskBadge(w.risk.level)}${stateBadge(w.state)}</div><div class="text-muted text-sm mt-1">${safe(w.profile.type)} · ${safe(w.business.city || 'Demo City')} · AI DEMO / SIMULATED AI ANALYSIS</div></div></div>${actionButton(w)}</div>
        ${demoNotice(false)}
        <div class="card mb-4" style="border-left:4px solid #6366f1"><div class="flex justify-between gap-3 flex-wrap"><div><div class="badge badge-purple">🤖 AI DECISION · TRANSPARENT</div><div style="font-weight:800;margin-top:10px">Why this route was created</div><div class="text-sm text-muted mt-1">${safe(w.profile.why)}</div></div><div style="min-width:170px"><div class="text-xs text-muted">AI RISK ASSESSMENT</div><div style="font-size:30px;font-weight:900;color:${w.risk.level==='LOW'?'#16a34a':w.risk.level==='HIGH'?'#dc2626':'#d97706'}">${w.risk.score}<span style="font-size:14px">/100</span></div>${riskBadge(w.risk.level)}</div></div><div class="info-box mt-3"><strong>Recommendation:</strong> ${safe(w.risk.recommendation)}</div></div>
        <div class="card mb-4"><div class="flex justify-between items-center mb-3"><div style="font-weight:800">Unified application timeline</div><div class="text-xs text-muted">Actual persisted workflow state</div></div>${timeline(w.state)}</div>
        <div class="grid-2" style="align-items:start">
          <div class="card"><div class="flex justify-between items-center mb-3"><div style="font-weight:800">AI-generated approval checklist</div><span class="text-xs text-muted">${done}/${w.requirements.length} complete</span></div>
          ${w.requirements.map(r=>`<div style="border:1px solid var(--border);border-radius:11px;padding:13px;margin-bottom:9px"><div class="flex justify-between gap-2"><div><div style="font-weight:750">${safe(r.name)}</div><div class="text-xs text-muted mt-1">${safe(r.department)} · est. ${r.estimated_days} days ${r.inspection_required?'· inspection required':''}</div></div>${stateBadge(r.status)}</div><details class="mt-2"><summary class="text-xs" style="cursor:pointer;color:#2563eb;font-weight:700">Why required &amp; documents</summary><div class="text-xs text-muted mt-2">${safe(r.why_required || 'Required by a configured demo rule.')}<br><strong>Required documents:</strong> ${r.documents.map(d=>safe(d.name)).join(', ') || 'Guided during application'}.</div></details></div>`).join('')}
          </div>
          <div class="flex flex-col gap-4">
            <div class="card"><div style="font-weight:800;margin-bottom:12px">Document guidance & AI pre-validation</div>${w.documents.map(d=>`<div style="padding:10px 0;border-bottom:1px solid #f1f5f9"><div class="flex justify-between"><div><strong class="text-sm">${safe(d.name)}</strong>${d.mandatory?' <span class="text-xs text-red">Required</span>':''}<div class="text-xs text-muted">${safe(d.reason)} · ${safe(d.format)} · max ${safe(d.max_size)}</div></div><div style="text-align:right">${stateBadge(d.status.replace(' ', '_'))}<div class="text-xs text-muted mt-1">${d.confidence}% confidence</div></div></div></div>`).join('')}<div class="text-xs text-muted mt-3">Upload → pre-validate → correct → revalidate is backed by deterministic demo logic. Existing applications also support View, Replace and Delete for draft documents.</div></div>
            <div class="card"><div style="font-weight:800;margin-bottom:10px">Verified business profile</div>${[['Business',w.verified_profile.name],['Owner',w.verified_profile.owner],['Address',w.verified_profile.address],['Type',w.verified_profile.business_type]].map(x=>`<div class="flex justify-between gap-3 text-sm" style="padding:7px 0;border-bottom:1px solid #f1f5f9"><span class="text-muted">${x[0]}</span><span style="text-align:right;font-weight:600">${safe(x[1])}</span></div>`).join('')}<div class="success-box mt-3 text-sm">✓ ${safe(w.verified_profile.reuse_message)}</div></div>
          </div>
        </div>
        <div class="grid-2 mt-4" style="align-items:start"><div class="card"><div style="font-weight:800;margin-bottom:12px">Parallel department processing</div>${w.requirements.map(r=>`<div class="mb-3"><div class="flex justify-between text-sm"><span>${safe(r.department)}</span>${stateBadge(r.status)}</div><div class="progress-track mt-1"><div class="progress-fill" style="width:${r.status==='APPROVED'?'100':r.status.includes('INSPECTION')?'65':r.status==='UNDER_REVIEW'?'58':'36'}%;background:${r.status==='APPROVED'?'linear-gradient(to right,#22c55e,#16a34a)':'linear-gradient(to right,#818cf8,#4f46e5)'}"></div></div></div>`).join('')}<div class="text-xs text-muted">Independent departments are coordinated in parallel; applicants do not route applications manually.</div></div>
          <div class="card"><div style="font-weight:800;margin-bottom:12px">AI activity & audit trail</div>${w.activity.map((a,i)=>`<div class="flex gap-3" style="padding:0 0 ${i===w.activity.length-1?0:12}px"><div style="width:8px;height:8px;background:${a.kind==='alert'?'#f59e0b':a.kind==='inspection'?'#6366f1':'#22c55e'};border-radius:50%;margin-top:5px;flex-shrink:0"></div><div><div class="text-xs text-muted">${safe(a.time)}</div><div class="text-sm">${safe(a.action)}</div></div></div>`).join('')}</div></div>
        <div class="card mt-4"><div class="flex justify-between items-center mb-3"><div><div style="font-weight:800">AI-matched government schemes</div><div class="text-xs text-muted">Potential matches based on the simulated business profile — not a representation of eligibility.</div></div><span class="badge badge-amber">DEMO SCHEME DATA</span></div><div class="grid-3">${w.schemes.map(s=>`<div style="border:1px solid var(--border);border-radius:10px;padding:12px"><strong class="text-sm">${safe(s.name)}</strong><div class="text-xs text-muted mt-1">${safe(s.reason)}</div><div class="text-xs mt-2" style="color:#16a34a">✓ ${safe(s.status)}</div></div>`).join('') || '<div class="text-muted">No demo scheme match.</div>'}</div></div>`;
    } catch (error) { showError('Failed to load AI workflow: ' + error.message); }
  };

  window.aiRevalidate = async function (id) {
    try { await api('POST', `/ai-agent/workflow/${id}/revalidate`, {}); toast('Corrected document revalidated at 96% confidence.', 'success'); navigate('ai-workflow', { businessId:id }); }
    catch (error) { toast(error.message, 'error'); }
  };
  window.aiApprove = async function (id) {
    try { const d = await api('POST', `/ai-agent/workflow/${id}/approve`, {}); toast('Accountable demo decision recorded; prototype certificate issued.', 'success'); navigate('ai-workflow', { businessId:id }); }
    catch (error) { toast(error.message, 'error'); }
  };

  PAGES['ai-dashboard'] = async function () {
    showLoadingUpgrade();
    try {
      const [data, all] = await Promise.all([api('GET', '/ai-agent/dashboard'), workflows()]);
      const s = data.stats || {};
      document.getElementById('page-content').innerHTML = `
        <div class="flex justify-between items-start flex-wrap gap-3 mb-3"><div><div class="page-title">🤖 AI Compliance Agent</div><div class="page-subtitle">Automated compliance intelligence &amp; workflow orchestration · <strong style="color:#6366f1">AI DEMO</strong></div></div><button class="btn btn-primary" onclick="navigate('demo-workflows')">Explore workflows →</button></div>
        ${demoNotice(false)}
        <div class="grid-4 mb-4">${[['Active applications',s.active_applications,'📋'],['Automatically processed',s.auto_processed,'✨'],['Automation rate',`${s.automation_rate}%`,'⚡'],['Documents validated',s.docs_validated,'📄'],['Departments coordinated',s.depts_coordinated,'🔀'],['Inspections scheduled',s.inspections_scheduled,'🔍'],['SLA alerts',s.sla_alerts,'⏰'],['Exceptions',s.exceptions,'⚠️'],['Avg. processing time',`${s.avg_processing_days} days`,'⏱️'],['Estimated time saved',`${s.time_saved_pct}%`,'📈']].map(x=>`<div class="stat-card"><div class="stat-icon" style="background:#eef2ff">${x[2]}</div><div class="stat-value" style="font-size:${String(x[1]).length>6?'20':'28'}px">${x[1]}</div><div class="stat-label">${x[0]}</div></div>`).join('')}</div>
        <div class="grid-2" style="align-items:start"><div class="card"><div class="flex justify-between items-center mb-3"><div style="font-weight:800">Live-looking AI activity stream</div><span class="badge badge-purple">SIMULATED</span></div>${(data.activity || []).slice(0,12).map(a=>`<div class="flex gap-3" style="padding:0 0 13px"><div style="font-size:17px">${a.icon || '🤖'}</div><div><div class="text-xs text-muted">${safe(a.time)}</div><div class="text-sm">${safe(a.action)}</div></div></div>`).join('')}</div><div class="card"><div style="font-weight:800;margin-bottom:4px">Five differentiated business journeys</div><div class="text-muted text-sm mb-3">Rules, risk, documents and inspection tasks change with business activity.</div>${all.map(b=>`<button style="width:100%;text-align:left;background:white;border:1px solid var(--border);border-radius:10px;padding:11px;margin-bottom:8px;cursor:pointer" onclick="navigate('ai-workflow',{businessId:'${b.id}'})"><div class="flex justify-between"><span><span style="font-size:18px">${b.icon}</span> <strong>${safe(b.name)}</strong></span>${riskBadge(b.risk)}</div><div class="text-xs text-muted mt-1">${b.requirements} requirements · ${safe(b.inspection_status)}</div></button>`).join('')}</div></div>`;
    } catch (error) { showError('Failed to load AI compliance dashboard: ' + error.message); }
  };

  PAGES['ai-queue'] = async function () {
    showLoadingUpgrade();
    try {
      const { queue } = await api('GET', '/ai-agent/queue');
      document.getElementById('page-content').innerHTML = `
        <div class="page-title">🤖 AI Decision Queue</div>
        <div class="page-subtitle">Live applications awaiting (or ready for) AI compliance review. Decisions are computed by the deterministic rule engine.</div>
        ${demoNotice(false)}
        <div class="card" style="padding:0;overflow:hidden"><div class="table-wrap"><table><thead><tr><th>Application</th><th>Business</th><th>Approval</th><th>Status</th><th>Risk</th><th>AI decision</th><th>Actions</th></tr></thead><tbody>
        ${queue.map(x=>`<tr><td><strong>${safe(x.application_number)}</strong></td><td>${safe(x.business)}</td><td>${safe(x.approval_type)}</td><td>${stateBadge(x.status)}</td><td>${riskBadge(x.risk.level)} (${x.risk.score})</td><td><span class="badge ${x.decision==='APPROVE'?'badge-green':x.decision==='REJECT'?'badge-red':'badge-amber'}">${safe(x.decision)}</span> <span class="text-xs text-muted">${x.confidence}%</span><div class="text-xs text-muted mt-1">${safe(x.reason)}</div></td><td><button class="btn btn-outline btn-sm" onclick="navigate('application-detail',{applicationId:'${x.id}'})">Decision panel</button><button class="btn btn-primary btn-sm" onclick="runAiReview('${x.id}')">Run review</button></td></tr>`).join('') || '<tr><td colspan="7" style="text-align:center;padding:48px;color:var(--slate)">No applications awaiting AI review.</td></tr>'}
        </tbody></table></div></div>`;
    } catch (error) { showError('Failed to load AI decision queue: ' + error.message); }
  };

  /* ── Licence Knowledge Centre — ONLY 6 official licences ──── */
  const LICENCE_KNOWLEDGE_CODES = ['FSSAI', 'FIRE_NOC', 'GST_REG', 'LABOUR_REG', 'POLLUTION_CTO', 'ELEC_SAFETY'];
  const LICENCE_KNOWLEDGE_INFO = {
    FIRE_NOC: 'Fire NOC application is handled by the relevant State/UT Fire & Emergency Services authority. Application is state/UT dependent — verify with your local fire authority.',
    ELEC_SAFETY: 'Electrical safety inspection/certification may be handled by the State/UT Electrical Inspectorate. CEA does not issue every state certificate.',
  };
  PAGES['licence-knowledge'] = async function () {
    showLoadingUpgrade();
    try {
      const d = await api('GET', '/approvals/types');
      const allTypes = (d.approval_types || []);
      const types = allTypes.filter(t => LICENCE_KNOWLEDGE_CODES.includes(t.code)).sort((a,b) => (a.name||'').localeCompare(b.name||''));
      document.getElementById('page-content').innerHTML = `
        <div class="mb-4">
          <h2 style="font-size:18px;font-weight:800;margin:0">📚 Licence Knowledge Centre</h2>
          <div class="text-sm text-muted">Official reference for the 6 required licences — verify current requirements with the authority before submission.</div>
        </div>
        <div class="warning-box mb-4" style="border-left:4px solid #f59e0b;background:#fffbeb;color:#92400e">
          <strong>⚠ Verify before submission:</strong> The sources below are official government references. Requirements may change — always verify the latest rules, fees, and documents directly with the issuing authority or their portal before submitting your application.
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px">
          ${types.map(t => {
            const sources = t.official_sources || [];
            const extraInfo = LICENCE_KNOWLEDGE_INFO[t.code] || '';
            return `<div class="card" style="text-align:left">
              <div style="font-weight:750;font-size:15px;margin-bottom:6px">${safe(t.name)}</div>
              <div class="text-xs text-muted mb-2">${safe(t.department?.name || '')} · SLA ${t.sla_days || '—'} days${t.requires_inspection ? ' · Inspection required' : ''}</div>
              <div class="text-sm" style="margin-bottom:8px">${safe(t.why_required || t.description || '')}</div>
              ${sources.length ? `<div class="text-xs text-muted"><strong>Official sources:</strong><ul style="margin:4px 0 0 16px;padding:0">${sources.map(s => `<li><a href="${safe(s.url)}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;font-weight:600">${safe(s.name)}</a></li>`).join('')}</ul></div>` : ''}
              ${extraInfo ? `<div class="text-xs mt-2" style="color:#92400e"><strong>Note:</strong> ${safe(extraInfo)}</div>` : ''}
            </div>`;
          }).join('')}
        </div>`;
    } catch (e) { showError('Failed to load licence knowledge: ' + e.message); }
  };

  PAGES['inspector-dashboard'] = async function () {
    showLoadingUpgrade();
    try {
      const [d, od] = await Promise.all([
        api('GET', '/inspector/dashboard').catch(() => ({ inspections: [] })),
        api('GET', '/officer/dashboard').catch(() => ({})),
      ]);
      const insps = d.inspections || [];
      const s = od.stats || {};
      const allApps = od.actionable_applications || [];
      const allByStatus = s.by_status || {};
      const term = ['APPROVED','REJECTED','EXPIRED'];
      const statTile = (label, value, color) =>
        `<div class="stat-card"><div class="stat-icon" style="background:#eef2ff;color:${color};font-size:20px">${value || 0}</div><div class="stat-label">${label}</div></div>`;

      const pendingReview = allApps.filter(a => a.status === 'DECISION_PENDING' && a.ai_reviewed_at);
      const awaitingDocs  = allApps.filter(a => a.status === 'CORRECTION_REQUIRED');
      const underInsp     = allApps.filter(a => a.status === 'INSPECTION_SCHEDULED' || a.status === 'INSPECTION_STARTED');
      const finalApproval = allApps.filter(a => a.status === 'INSPECTION_COMPLETED' || a.status === 'INSPECTION_PASSED');
      const completed     = allApps.filter(a => term.includes(a.status));

      function applicationRow(a) {
        const open = `navigate('officer-app-detail',{applicationId:'${a.id}'})`;
        let btns = '';
        if (a.status === 'DECISION_PENDING' && a.ai_reviewed_at) {
          btns = `<button class="btn btn-outline btn-sm" onclick="${open}">Review</button>`;
        } else if (a.status === 'CORRECTION_REQUIRED') {
          btns = `<button class="btn btn-outline btn-sm" onclick="${open}">View</button>`;
        } else if (a.status === 'INSPECTION_SCHEDULED' || a.status === 'INSPECTION_STARTED') {
          btns = `<button class="btn btn-outline btn-sm" onclick="${open}">Open Inspection</button>`;
        } else if (a.status === 'INSPECTION_COMPLETED' || a.status === 'INSPECTION_PASSED') {
          btns = `<button class="btn btn-primary btn-sm" onclick="${open}">Final Approval</button>`;
        } else if (a.status === 'APPROVED') {
          btns = `<button class="btn btn-outline btn-sm" onclick="${open}">View Certificate</button>`;
        } else if (a.status === 'REJECTED') {
          btns = `<button class="btn btn-outline btn-sm" onclick="${open}">View</button>`;
        }
        const sla = a.sla_deadline ? (() => {
          const d = Math.round((new Date(a.sla_deadline) - new Date()) / 86400000);
          return d < 0 ? '<span class="badge badge-red">SLA breached</span>'
                       : d <= 3 ? `<span class="badge badge-amber">${d}d to SLA</span>`
                                : '<span class="badge badge-green">Within SLA</span>';
        })() : '—';
        return `<tr>
          <td><strong>${safe(a.approval_type_name || '—')}</strong><div class="text-xs text-muted">${safe(a.application_number)}</div></td>
          <td><strong>${safe(a.business_name || '—')}</strong></td>
          <td>${stateBadge(a.status)}</td>
          <td>${sla}</td>
          <td>${btns}</td>
        </tr>`;
      }

      document.getElementById('page-content').innerHTML = `
        <div class="page-title">Licence Officer / Inspector Dashboard</div>
        <div class="page-subtitle">Arjun Singh · Application Review • Inspection • Final Approval — one accountable officer for the entire licence lifecycle.</div>
        ${demoNotice(true)}

        <div class="grid-4 mb-4">
          ${statTile('Action Required', s.actionable || 0, '#1d4ed8')}
          ${statTile('Awaiting Documents', s.awaiting_documents || 0, '#b45309')}
          ${statTile('Under Inspection', s.under_inspection || 0, '#6d28d9')}
          ${statTile('Completed', s.completed || 0, '#047857')}
        </div>

        <div class="card mb-3" style="padding:0;overflow:hidden">
          <div style="padding:16px 20px;border-bottom:1px solid var(--border)">
            <div class="flex justify-between items-center">
              <div>
                <strong style="font-weight:800">ACTION REQUIRED</strong>
                <span class="badge badge-blue" style="margin-left:8px">${pendingReview.length} Pending Review</span>
                ${finalApproval.length ? `<span class="badge badge-green" style="margin-left:6px">${finalApproval.length} Final Approval Ready</span>` : ''}
              </div>
            </div>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Licence Type</th><th>Business</th><th>Status</th><th>SLA</th><th>Actions</th></tr></thead><tbody>
            ${pendingReview.map(applicationRow).join('')}
            ${finalApproval.map(applicationRow).join('')}
            ${(pendingReview.length + finalApproval.length) === 0 ? '<tr><td colspan="5" style="text-align:center;padding:28px;color:var(--slate)">No action required at this time.</td></tr>' : ''}
          </tbody></table></div>
        </div>

        <div class="card mb-3" style="padding:0;overflow:hidden">
          <div style="padding:16px 20px;border-bottom:1px solid var(--border)">
            <strong style="font-weight:800">AWAITING DOCUMENTS</strong>
            <span class="badge badge-amber" style="margin-left:8px">${awaitingDocs.length}</span>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Licence Type</th><th>Business</th><th>Status</th><th>SLA</th><th>Actions</th></tr></thead><tbody>
            ${awaitingDocs.map(applicationRow).join('')}
            ${awaitingDocs.length === 0 ? '<tr><td colspan="5" style="text-align:center;padding:28px;color:var(--slate)">No applications awaiting documents.</td></tr>' : ''}
          </tbody></table></div>
        </div>

        <div class="card mb-3" style="padding:0;overflow:hidden">
          <div style="padding:16px 20px;border-bottom:1px solid var(--border)">
            <strong style="font-weight:800">UNDER INSPECTION</strong>
            <span class="badge badge-purple" style="margin-left:8px">${underInsp.length}</span>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Licence Type</th><th>Business</th><th>Status</th><th>SLA</th><th>Actions</th></tr></thead><tbody>
            ${underInsp.map(applicationRow).join('')}
            ${underInsp.length === 0 ? '<tr><td colspan="5" style="text-align:center;padding:28px;color:var(--slate)">No inspections currently underway.</td></tr>' : ''}
          </tbody></table></div>
        </div>

        <div class="card" style="padding:0;overflow:hidden">
          <div style="padding:16px 20px;border-bottom:1px solid var(--border);font-weight:800">My Inspections</div>
          <div class="table-wrap"><table><thead><tr><th>Approval Type</th><th>Business</th><th>Status</th><th>Scheduled</th><th>Actions</th></tr></thead><tbody>
            ${insps.map(insp => {
              const actions = { ASSIGNED: '📅 Schedule', SCHEDULED: '📝 Report', COMPLETED: 'Reported' };
              const fn = insp.status === 'ASSIGNED' ? `showScheduleModal('${insp.id}')` : insp.status === 'SCHEDULED' ? `showReportModal('${insp.id}','${(insp.application?.approval_type_name||'').replace(/'/g,'')}','${(insp.business?.name||'').replace(/'/g,'')}')` : '';
              return `<tr>
                <td><strong>${safe(insp.application?.approval_type_name || '—')}</strong></td>
                <td><strong>${safe(insp.business?.name || '—')}</strong><br><span class="text-xs text-muted">${safe(insp.business?.city || '')}</span></td>
                <td>${stateBadge(insp.status)}<br><span class="text-xs text-muted">${insp.overall_result ? safe(insp.overall_result) : ''}</span></td>
                <td>${fmtDate(insp.scheduled_date) || 'Not scheduled'}</td>
                <td>${fn ? `<button class="btn btn-primary btn-sm" onclick="${fn}">${actions[insp.status]}</button>` : '<span class="text-xs text-muted">Reported</span>'}</td>
              </tr>`;
            }).join('') || '<tr><td colspan="5" style="padding:40px;text-align:center;color:var(--slate)">No inspections assigned to you yet.</td></tr>'}
          </tbody></table></div>
        </div>
      `;
    } catch (error) { showError('Failed to load inspector dashboard: ' + error.message); }
  };
  window.startDemoInspection = async function(id) { try { await api('POST', `/ai-agent/inspection/${id}/start`, {}); toast('Inspection started; workflow state updated.', 'success'); navigate('inspector-dashboard'); } catch (e) { toast(e.message, 'error'); } };
  window.completeDemoInspection = async function(id) { try { await api('POST', `/ai-agent/inspection/${id}/complete`, {result:'PASS'}); toast('PASS report submitted. AI updated the parallel workflow.', 'success'); navigate('inspector-dashboard'); } catch (e) { toast(e.message, 'error'); } };

  PAGES['admin-dashboard'] = async function () {
    showLoadingUpgrade();
    try {
      const [gov, dashboard] = await Promise.all([api('GET', '/ai-agent/governance'), api('GET', '/admin/dashboard')]);
      const s = dashboard.stats || {}, m = gov.metrics || {};
      document.getElementById('page-content').innerHTML = `
        <div class="flex justify-between items-start flex-wrap gap-3 mb-3"><div><div class="page-title">Admin governance &amp; exceptions</div><div class="page-subtitle">AI automates routine work; Admins provide oversight, exception handling and accountable decisions.</div></div><button class="btn btn-danger" onclick="confirmDemoReset()">↻ Reset demo environment</button></div>${demoNotice(false)}
        <div class="grid-4 mb-4">${[['Total applications',s.total_applications,'📋'],['Automated applications',`${m.automation_rate}%`,'✨'],['Exceptions',gov.exceptions.length,'⚠️'],['SLA compliance',`${m.sla_compliance}%`,'⏰'],['Time saved',`${m.time_saved}%`,'📈'],['Inspections',s.total_inspections,'🔍'],['Incomplete',m.incomplete_applications,'📄'],['Certificates',s.total_certificates,'🏅']].map(x=>`<div class="stat-card"><div class="stat-icon" style="background:#eef2ff">${x[2]}</div><div class="stat-value">${x[1]}</div><div class="stat-label">${x[0]}</div></div>`).join('')}</div>
        <div class="grid-2" style="align-items:start"><div class="card"><div class="flex justify-between items-center mb-3"><div style="font-weight:800">AI exception queue</div><span class="badge badge-red">${gov.exceptions.length} needs attention</span></div>${gov.exceptions.map(e=>`<div style="border:1px solid #fecaca;border-radius:10px;padding:13px;margin-bottom:10px"><div class="flex justify-between gap-2"><strong>${safe(e.application)}</strong>${riskBadge(e.risk)}</div><div class="text-sm mt-2"><strong>Reason:</strong> ${safe(e.reason)}</div><div class="text-xs text-muted mt-1">AI recommendation: ${safe(e.recommendation)}</div><div class="flex gap-2 flex-wrap mt-3"><button class="btn btn-primary btn-sm" onclick="adminException('${e.business_id}','ACCEPT')">Accept recommendation</button><button class="btn btn-outline btn-sm" onclick="adminException('${e.business_id}','REQUEST_INFO')">Request information</button><button class="btn btn-outline btn-sm" onclick="adminException('${e.business_id}','OVERRIDE')">Override</button><button class="btn btn-outline btn-sm" onclick="navigate('ai-workflow',{businessId:'${e.business_id}'})">Review</button></div></div>`).join('') || '<div class="success-box">No exceptional cases in the current demo state.</div>'}</div>
        <div class="card"><div style="font-weight:800">AI delay analysis</div><div class="text-muted text-sm mt-1">${safe(gov.delay_analysis.insight)}</div><div class="grid-3 mt-4"><div><div class="text-xs text-muted">Department</div><strong>${safe(gov.delay_analysis.department)}</strong></div><div><div class="text-xs text-muted">Avg. processing</div><strong>${gov.delay_analysis.average_processing_days} days</strong></div><div><div class="text-xs text-muted">SLA breach</div><strong style="color:#dc2626">${gov.delay_analysis.breach_rate}%</strong></div></div><hr class="divider"><div style="font-weight:800">Demo data management</div><p class="text-sm text-muted mt-1">Restores the five sample businesses and their simulated states. Finalized audit entries remain retained for accountability.</p>    <button class="btn btn-outline mt-2" onclick="confirmDemoReset()">Restore sample data</button></div></div>`;
    } catch (error) { showError('Failed to load governance dashboard: ' + error.message); }
  };
  window.adminException = async function(id, action) { try { await api('POST', `/ai-agent/exception/${id}/action`, { action, notes:'Recorded through Admin governance dashboard.' }); toast('Admin action recorded in the audit trail.', 'success'); navigate('admin-dashboard'); } catch (e) { toast(e.message, 'error'); } };
  window.confirmDemoReset = function () { document.getElementById('modal-title').textContent = 'Reset demo environment?'; document.getElementById('modal-body').innerHTML = `<p class="text-sm text-muted">This restores the five sample businesses and their demo workflows. It does not represent a real government record.</p><div class="flex gap-3 mt-4"><button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button><button class="btn btn-danger" style="flex:1" onclick="runDemoReset()">Reset demo</button></div>`; openModal(); };
  window.runDemoReset = async function () { try { await api('POST', '/ai-agent/demo-reset', {}); closeModal(); toast('Five sample workflows restored.', 'success'); navigate('admin-dashboard'); } catch (e) { toast(e.message, 'error'); } };

  PAGES['ai-audit'] = async function () {
    showLoadingUpgrade();
    try {
      const all = await workflows();
      const detail = await Promise.all(all.map(x=>api('GET', `/ai-agent/workflow/${x.id}`)));
      const rows = detail.flatMap(d => (d.workflow.activity || []).map(a => ({ ...a, business:d.workflow.business.name }))).slice(0, 50);
      document.getElementById('page-content').innerHTML = `<div class="page-title">AI audit trail</div><div class="page-subtitle">Timestamped simulated AI actions with the business context and a human-accountability boundary.</div>${demoNotice(false)}<div class="card" style="padding:0;overflow:hidden"><div class="table-wrap"><table><thead><tr><th>Time</th><th>Business</th><th>Action / reason</th><th>Source</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${safe(x.time)}</td><td><strong>${safe(x.business)}</strong></td><td>${safe(x.action)}</td><td><span class="badge badge-purple">AI DEMO</span></td></tr>`).join('')}</tbody></table></div></div>`;
    } catch (error) { showError('Failed to load AI audit trail: ' + error.message); }
  };

  /* Actual draft-delete, preview, replace and document validation controls. */
  PAGES['applications'] = async function () {
    showLoadingUpgrade();
    try {
      const list = (await api('GET', '/applications/')).applications || [];
      document.getElementById('page-content').innerHTML = `<div class="flex justify-between items-start mb-3"><div><div class="page-title">Applications</div><div class="page-subtitle">Open an application to view document guidance, validation, status history and audit records.</div></div>${user.role==='APPLICANT'?'<button class="btn btn-primary" onclick="navigate(\'create-business\')">+ Register business</button>':''}</div><div class="card" style="padding:0;overflow:hidden"><div class="table-wrap"><table><thead><tr><th>Application</th><th>Business</th><th>Status</th><th>SLA</th><th>Actions</th></tr></thead><tbody>${list.map(a=>{ const done=['APPROVED','REJECTED','EXPIRED'].includes(a.status); let slaCell='—'; if(a.sla_deadline&&!done){ const days=Math.round((new Date(a.sla_deadline)-new Date())/86400000); slaCell = days<0?`<span class="badge badge-red">🔴 SLA breached</span>`:days<=3?`<span class="badge badge-amber">⚠ ${days}d to deadline</span>`:`<span class="badge badge-green">✓ within SLA</span><div class="text-xs text-muted mt-1">${fmtDate(a.sla_deadline)}</div>`; } else if(a.sla_deadline){ slaCell=`<span class="text-muted text-xs">${fmtDate(a.sla_deadline)}</span>`; } return `<tr><td><strong>${safe(a.approval_type_name)}</strong><div class="text-xs text-muted">${safe(a.application_number)}</div></td><td>${safe(a.business_name)}</td><td>${stateBadge(a.status)}</td><td>${slaCell}</td><td><button class="btn btn-outline btn-sm" onclick="navigate('application-detail',{applicationId:'${a.id}'})">View</button>${['DRAFT','CORRECTION_REQUIRED'].includes(a.status)?` <button class="btn btn-danger btn-sm" onclick="confirmDraftDelete('${a.id}')">Delete</button>`:''}</td></tr>`; }).join('') || '<tr><td colspan="5" style="text-align:center;padding:48px;color:var(--slate)">No applications yet.</td></tr>'}</tbody></table></div></div>`;
    } catch (e) { showError('Failed to load applications: ' + e.message); }
  };
  PAGES['application-detail'] = async function(params) {
    const id = params?.applicationId || window._pageParams?.applicationId;
    if (!id) { navigate('applications'); return; }
    // Remember where this application was opened from so the Back button and
    // the approve/reject decision return to the correct previous view.
    const origin = window._prevPage;
    window._appReturnTo = ['applications', 'business-detail', 'ai-queue', 'admin-dashboard', 'inspector-dashboard'].includes(origin) ? origin : 'applications';
    showLoadingUpgrade();
    try {
      const [appData, docData, aiData, repoData] = await Promise.all([
        api('GET', `/applications/${id}`),
        api('GET', `/documents/application/${id}`),
        api('GET', `/ai-agent/application/${id}/decision`).catch(() => null),
        api('GET', '/documents/repository').catch(() => ({ documents: [] })),
      ]);
      const app = appData.application, reqs = docData.requirements || [];
      const assessment = aiData?.assessment || null;
      const repoDocs = repoData.documents || [];
      // Verify-once / reuse-everywhere: a previously verified document of the
      // same business that satisfies the same requirement can be reused.
      const reusableFor = {};
      reqs.forEach(r => {
        if (r.document) return;
        const candidates = repoDocs.filter(d =>
          d.business_id === app.business_id &&
          d.verification_status === 'VERIFIED' &&
          (d.doc_type === r.requirement.code || d.requirement_id === r.requirement.id)
        );
        if (candidates.length) reusableFor[r.requirement.id] = candidates[0];
      });
      const isApplicant = user && user.role === 'APPLICANT';
      const isAdmin = user && user.role === 'ADMIN';
      const isInspector = user && user.role === 'INSPECTOR';
      // Applicant may (re)upload documents while any document stage is open —
      // including after an officer rejects a single document (UNDER_REVIEW /
      // SUBMITTED) or requests additional documents. Delete stays limited to
      // drafts/corrections (matches the backend guard).
      const editable = isApplicant && ['DRAFT','SUBMITTED','UNDER_REVIEW','DOCUMENT_VALIDATION','CORRECTION_REQUIRED','ADDITIONAL_DOCUMENTS_REQUIRED'].includes(app.status);
      const canSubmit = isApplicant && app.status === 'DRAFT';
      const canCorrect = isApplicant && app.status === 'CORRECTION_REQUIRED';
      // An official decision is only offered once the AI review has passed and,
      // where an inspection was required, the inspection has been completed.
      const canDecide = ['DECISION_PENDING', 'INSPECTION_COMPLETED'].includes(app.status) && isAdmin;
      const risk = assessment?.risk || null;
      const checks = assessment?.checks || {};
      const decisionColor = assessment?.decision === 'APPROVE' ? '#16a34a' : assessment?.decision === 'REJECT' ? '#dc2626' : '#d97706';

      const journeyMap = { DRAFT:0, SUBMITTED:1, AI_PROCESSING:1, AI_CHECK_COMPLETE:1, CORRECTION_REQUIRED:1, DOCUMENT_VALIDATION:1, SUBMITTED_TO_AUTHORITY:2, ASSIGNED_TO_OFFICER:2, UNDER_REVIEW:2, DECISION_PENDING:3, INSPECTION_REQUIRED:3, INSPECTION_SCHEDULED:3, INSPECTION_COMPLETED:3, INSPECTION_PASSED:3, APPROVED:4, REJECTED:4 };
      const journeyStep = journeyMap[app.status] !== undefined ? journeyMap[app.status] : 1;
      const journeyNames = ['Application','Documents','AI Review','Inspection','Decision'];
      // A final decision completes every stage. Decision shows a green ✓ when
      // approved and a red ✕ when rejected — never an incomplete step.
      const finalDecision = app.status === 'APPROVED' ? 'approved' : (app.status === 'REJECTED' ? 'rejected' : null);
      const journeyHTML = journeyNames.map((s,i) => {
        const isLast = i === journeyNames.length - 1;
        const done = finalDecision !== null || i < journeyStep;
        const active = !done && i === journeyStep;
        let circleClass = done ? 'done' : (active ? 'active' : '');
        let circleText = done ? '✓' : (i + 1);
        if (finalDecision === 'rejected' && isLast) { circleClass = 'rejected'; circleText = '✕'; }
        return `<div class="flex items-center" style="flex-shrink:0"><div class="step-col"><div class="step-circle ${circleClass}">${circleText}</div><div class="step-label ${done || active ? 'active' : ''}">${s}</div></div>${!isLast ? `<div class="step-line ${done ? 'done' : ''}" style="margin-top:18px"></div>` : ''}</div>`;
      }).join('');

      const statusFor = (r) => {
        // Effective status per requirement; the backend reports NOT_UPLOADED
        // when nothing was uploaded yet, otherwise the latest document's state.
        const vs = (r.status || (r.document && (r.document.verification_status || 'PENDING')) || 'NOT_UPLOADED').toUpperCase();
        if (vs === 'NOT_UPLOADED') return { label: r.requirement.is_mandatory ? 'Required' : 'Optional', cls: r.requirement.is_mandatory ? 'badge-amber' : 'badge-slate' };
        if (vs === 'VERIFIED' || vs === 'APPROVED') return { label: 'Verified', cls: 'badge-green' };
        if (vs === 'REJECTED') return { label: 'Rejected', cls: 'badge-red' };
        if (vs === 'RESUBMISSION_REQUIRED' || vs === 'NEEDS_CORRECTION') return { label: 'Resubmission Required', cls: 'badge-amber' };
        if (vs === 'VALIDATION_PENDING') return { label: 'Validation Pending', cls: 'badge-amber' };
        if (vs === 'UNDER_OFFICER_REVIEW' || vs === 'UNDER_REVIEW') return { label: 'Officer Review', cls: 'badge-blue' };
        if (vs === 'UPLOADED') return { label: 'Uploaded', cls: 'badge-blue' };
        return { label: readable(vs), cls: 'badge-blue' };
      };

      const aiPanel = assessment ? `
        <div class="card mb-4" style="border-left:4px solid #6366f1">
          <div class="flex justify-between items-center flex-wrap gap-3 mb-3">
            <div><div class="badge badge-purple">🤖 AI COMPLIANCE CHECK</div><span class="text-xs text-muted ml-2">${assessment.used_llm ? 'Local model enriched this explanation.' : 'Deterministic rule engine.'}</span></div>
            <span style="font-size:15px;font-weight:800;color:${decisionColor}">${safe(assessment.decision)} · ${assessment.confidence}% confidence</span>
          </div>
          <div class="info-box mb-3" style="background:#eef2ff;border-color:#c7d2fe">${safe(assessment.explanation)}</div>
          <div class="grid-2" style="align-items:start">
            <div><div class="text-xs text-muted mb-2" style="font-weight:700">RISK ASSESSMENT</div>
              <div class="flex items-center gap-3"><span style="font-size:28px;font-weight:900;color:${risk?.level==='LOW'?'#16a34a':risk?.level==='HIGH'?'#dc2626':'#d97706'}">${risk?.score||0}<span style="font-size:13px">/100</span></span>${riskBadge(risk?.level)}</div>
              <div class="text-xs text-muted mt-2">${(risk?.factors||[]).map(f=>`<div>• ${safe(f.factor)} (${safe(f.impact)})</div>`).join('') || 'No risk factors recorded.'}</div></div>
            <div><div class="text-xs text-muted mb-2" style="font-weight:700">COMPLIANCE CHECKS</div>
              <div class="flex flex-col gap-1 text-sm">
                <div class="flex justify-between"><span>Checklist complete</span>${checks.checklist_complete?'<span style="color:#16a34a">✓ Yes</span>':'<span style="color:#d97706">✗ No</span>'}</div>
                <div class="flex justify-between"><span>Documents</span>${stateBadge(checks.documents?.status)}</div>
                <div class="flex justify-between"><span>Inspection</span><span>${safe(checks.inspection?.status)}${checks.inspection?.result?' · '+safe(checks.inspection.result):''}</span></div>
              </div></div>
          </div>
          <details class="mt-3"><summary class="text-xs" style="cursor:pointer;color:#2563eb;font-weight:700">Evaluated checklist (${(assessment.checklist||[]).length} items)</summary>
            <div class="mt-2 flex flex-col gap-1">${(assessment.checklist||[]).map(c=>`<div class="flex justify-between gap-3 text-xs py-1" style="border-bottom:1px solid #f1f5f9"><span>${safe(c.code)} — ${safe(c.name)}</span><span>${c.mandatory?'<span class="badge badge-amber">MANDATORY</span>':'<span class="badge badge-slate">OPTIONAL</span>'} ${c.has_application?'✓ present':'<span style="color:#d97706">not applied</span>'}</span></div>`).join('')}</div>
          </details>
          <div class="text-xs text-muted mt-3">⚠️ The AI recommendation is advisory only — an accountable Admin or Inspector takes the final decision. Nothing is auto-approved.</div>
        </div>` : '';

      const actionButtons = `
        <div class="flex gap-2 flex-wrap">
          ${canSubmit ? `<button class="btn btn-primary btn-sm" onclick="submitApplication('${id}')">Submit Application</button>` : ''}
          ${canCorrect ? `<button class="btn btn-amber btn-sm" onclick="submitCorrection('${id}')">Submit Correction</button>` : ''}
          ${canDecide ? `<button class="btn btn-success btn-sm" onclick="showDecisionModal('${id}','APPROVE')">✓ Approve</button><button class="btn btn-danger btn-sm" onclick="showDecisionModal('${id}','REJECT')">✕ Reject</button>` : ''}
        </div>`;

      const certBanner = (app.status === 'APPROVED' && app.certificate) ? `
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:14px;padding:16px;margin-bottom:16px">
          <div class="flex justify-between items-start flex-wrap gap-2">
            <div><strong>🏅 Certificate Issued</strong><br><span class="text-sm">${safe(app.certificate.certificate_number)}</span><br><span class="text-xs text-muted">Valid until: ${fmtDate(app.certificate.valid_until)}</span></div>
            <button class="btn btn-success btn-sm" onclick="viewCertificate(${JSON.stringify(app.certificate).replace(/"/g,'&quot;')})">View Certificate</button>
          </div>
          <div class="text-xs mt-2" style="color:var(--amber)">⚠️ PROTOTYPE CERTIFICATE — Not a government-issued document</div>
        </div>` : '';

      const rejectBanner = (app.status === 'REJECTED' && app.rejection_reason) ? `
        <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:14px;padding:16px;margin-bottom:16px"><strong>✗ Rejected:</strong> ${safe(app.rejection_reason)}</div>` : '';
      const correctionBanner = (app.status === 'CORRECTION_REQUIRED' && app.correction_notes) ? `
        <div class="warning-box mb-4"><strong>⚠️ Correction Required:</strong> ${safe(app.correction_notes)}</div>` : '';

      document.getElementById('page-content').innerHTML = `
        <div class="flex justify-between items-start gap-3 mb-4">
          <div class="flex gap-3">
            <button class="btn btn-outline btn-sm btn-icon" onclick="navigate(window._appReturnTo || 'applications')">←</button>
            <div><div class="page-title" style="font-size:21px">${safe(app.approval_type_name)}</div><div class="text-muted text-sm">${safe(app.application_number)} · ${safe(app.business_name)}</div></div>
          </div>
          <div class="flex items-center gap-2 flex-wrap">${stateBadge(app.status)}${actionButtons}</div>
        </div>
        ${certBanner}${rejectBanner}${correctionBanner}
        <div class="card mb-4"><div class="flex items-center justify-between mb-3"><div style="font-weight:800">Application journey</div><span class="text-xs text-muted">${safe(app.department_name||'')}</span></div><div class="flex" style="overflow-x:auto;padding-bottom:8px">${journeyHTML}</div></div>
        ${aiPanel}
        <div class="grid-2" style="align-items:start">
          <div class="card">
            <div class="flex justify-between align-items-center mb-3"><strong>Document guidance & validation</strong>${editable?`<button class="btn btn-primary btn-sm" onclick="showAiUpload('${id}')">Upload</button>`:''}</div>
            ${reqs.length===0?'<p class="text-muted text-sm">No document requirements defined.</p>':''}
            ${reqs.map(r=>{ const st = statusFor(r); const reusable = reusableFor[r.requirement.id];
              const docNote = r.document && r.document.rejection_reason
                ? `<div class="text-xs mt-1" style="color:#dc2626"><strong>Officer's rejection reason:</strong> ${safe(r.document.rejection_reason)}</div>`
                : (r.document && r.document.verification_notes && ['NEEDS_CORRECTION','RESUBMISSION_REQUIRED'].includes(r.status)
                    ? `<div class="text-xs mt-1" style="color:#d97706"><strong>Resubmission required:</strong> ${safe(r.document.verification_notes)}</div>` : '');
              return `<div style="border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:8px"><div class="flex justify-between gap-2"><div><strong class="text-sm">${safe(r.requirement.name)}</strong>${r.requirement.is_mandatory?' <span class="text-xs text-red">Required</span>':''}<div class="text-xs text-muted mt-1">${safe(r.requirement.description)} · ${safe((r.requirement.allowed_formats||[]).join(', ').toUpperCase())} · max ${r.requirement.max_size_mb}MB</div></div><span class="badge ${st.cls}">${st.label}</span></div>${docNote}${r.document?`<div class="flex gap-2 mt-2"><button class="btn btn-outline btn-sm" onclick="previewDocument('${r.document.id}')">View</button>${editable?`<button class="btn btn-outline btn-sm" onclick="showAiUpload('${id}','${r.requirement.id}','${safe(r.requirement.code)}')">Replace</button>`:''}${(['DRAFT','CORRECTION_REQUIRED'].includes(app.status)&&editable)?`<button class="btn btn-danger btn-sm" onclick="deleteDemoDocument('${r.document.id}','${id}')">Delete</button>`:''}</div>`:editable?`<div class="flex gap-2 flex-wrap mt-2"><button class="btn btn-outline btn-sm" onclick="showAiUpload('${id}','${r.requirement.id}','${safe(r.requirement.code)}')">Upload</button>${reusable?`<button class="btn btn-outline btn-sm" onclick="reuseVerifiedDocument('${id}','${r.requirement.id}','${reusable.id}','${safe(r.requirement.name)}')" title="Reuse an already verified document from this business">↩ Reuse verified</button>`:''}</div>`:''}</div>`;}).join('')}
          </div>
          <div class="flex flex-col gap-4">
            <div class="card">
              <strong>Application details</strong>
              ${[['Department',app.department_name||'—'],['Submitted',fmtDate(app.submission_date)||'Not submitted'],['SLA deadline',fmtDate(app.sla_deadline)||'—'],['AI review', app.ai_decision?`${safe(app.ai_decision)} (${app.ai_decision_confidence||0}%)`:'Pending']].map(x=>`<div class="flex justify-between text-sm" style="padding:8px 0;border-bottom:1px solid #f1f5f9"><span class="text-muted">${x[0]}</span><span style="font-weight:600;text-align:right;max-width:60%">${safe(x[1])}</span></div>`).join('')}
            </div>
            <div class="card">
              <strong>Application timeline</strong>
              <div class="mt-3">${(app.status_history||[]).slice().reverse().map(x=>`<div class="flex gap-2" style="padding-bottom:12px"><div style="width:8px;height:8px;border-radius:50%;background:#6366f1;margin-top:6px;flex-shrink:0"></div><div>${stateBadge(x.status)}<div class="text-xs text-muted mt-1">${actorTag(x.changed_by_name)} <span style="color:#334155">${safe(x.changed_by_name||'System')}</span></div><div class="text-xs text-muted mt-1">${safe(x.notes||'State updated')} · ${fmtDateTime(x.created_at)}</div></div></div>`).join('')}</div>
            </div>
          </div>
        </div>`;
    } catch (e) { showError('Failed to load application details: ' + e.message); }
  };

  window.submitApplication = async function(id) {
    try {
      const d = await api('POST', `/applications/${id}/submit`, { force_submit: true });
      let aiMsg = '';
      try { const r = await api('POST', `/ai-agent/application/${id}/review`, {}); const a = r.assessment||{}; aiMsg = ` AI check: ${a.decision} (${a.confidence}% confidence) — ${a.reason||''}`; } catch(_) {}
      toast(`Application submitted successfully.${aiMsg}`,'success');
      navigate('application-detail', { applicationId: id });
    } catch(e) { toast(e.message,'error'); }
  };
  window.submitCorrection = async function(id) {
    try {
      await api('POST', `/applications/${id}/correction`, { notes: 'Correction submitted by applicant' });
      let aiMsg = '';
      try { const r = await api('POST', `/ai-agent/application/${id}/review`, {}); const a = r.assessment||{}; aiMsg = ` AI check: ${a.decision} (${a.confidence}% confidence) — ${a.reason||''}`; } catch(_) {}
      toast(`Correction submitted.${aiMsg}`,'success');
      navigate('application-detail', { applicationId: id });
    } catch(e) { toast(e.message,'error'); }
  };
  window.runAiReview = async function(id) {
    try { const r = await api('POST', `/ai-agent/application/${id}/review`, {}); const a = r.assessment||{}; toast(`AI review complete: ${a.decision} (${a.confidence}% confidence). Recorded to the audit trail.`,'success'); navigate('application-detail', { applicationId:id }); }
    catch (e) { toast(e.message, 'error'); }
  };
  window.showDecisionModal = function(appId, action) {
    const isApprove = action === 'APPROVE';
    document.getElementById('modal-title').textContent = isApprove ? '✓ Approve Application' : '✕ Reject Application';
    document.getElementById('modal-body').innerHTML = `
      <p class="text-sm text-muted mb-3">The AI recommendation is advisory. Your decision is recorded in the audit trail and, when approving, a prototype certificate and renewal record are generated.</p>
      <div class="form-group"><label>Reason <span style="color:var(--red)">*</span></label><textarea id="decision-reason" rows="4" placeholder="${isApprove?'Explain why this application meets all compliance requirements...':'Explain the reason for rejection...'}" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:8px;font-family:inherit;font-size:14px;resize:vertical"></textarea></div>
      <div class="flex gap-3">
        <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
        <button class="btn ${isApprove?'btn-success':'btn-danger'}" style="flex:1" id="decision-submit-btn" onclick="doDecision('${appId}','${action}')">${isApprove?'✓ Approve':'✕ Reject'}</button>
      </div>`;
    openModal();
  };
  window.doDecision = async function(appId, action) {
    const reason = document.getElementById('decision-reason')?.value?.trim();
    if(!reason) { toast('Please provide a reason','warning'); return; }
    const btn = document.getElementById('decision-submit-btn');
    if(btn) { btn.disabled = true; btn.textContent = '⏳ Processing...'; }
    try {
      await api('POST', `/admin/applications/${appId}/${action.toLowerCase()}`, { reason });
      toast(action === 'APPROVE' ? 'Application approved; certificate generated.' : 'Application rejected.', action === 'APPROVE' ? 'success' : 'warning');
      closeModal();
      // Return to the previous application/business view so the updated status
      // and counters are visible immediately without losing navigation state.
      navigate(window._appReturnTo || 'applications');
    } catch(e) { toast(e.message,'error'); if(btn){btn.disabled=false;btn.textContent=action==='APPROVE'?'✓ Approve':'✕ Reject';} }
  };
  window.confirmDraftDelete = function(id) { document.getElementById('modal-title').textContent = 'Delete draft application?'; document.getElementById('modal-body').innerHTML = `<p class="text-sm text-muted">This permanently removes the demo draft and associated draft documents. Finalized records are retained as an audit record.</p><div class="flex gap-3 mt-4"><button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button><button class="btn btn-danger" style="flex:1" onclick="runDraftDelete('${id}')">Delete</button></div>`; openModal(); };
  window.runDraftDelete = async function(id) { try { await api('DELETE', `/applications/${id}`); closeModal(); toast('Draft application deleted.', 'success'); navigate('applications'); } catch (e) { toast(e.message, 'error'); } };
  window.previewDocument = async function(id) { try { const d = await api('GET', `/documents/${id}/preview`); document.getElementById('modal-title').textContent = 'Document preview'; document.getElementById('modal-body').innerHTML = `<div class="warning-box mb-3">${safe(d.notice)}</div><div class="card"><strong>${safe(d.document.filename)}</strong><div class="text-sm text-muted mt-2">AI status: ${safe(d.document.verification_status)}<br>${safe(d.document.verification_notes||'Awaiting simulated analysis.')}</div>${d.preview_url?`<a class="btn btn-primary btn-sm mt-3" href="${safe(d.preview_url)}" target="_blank" rel="noopener">Open uploaded file</a>`:'<div class="text-xs text-muted mt-3">No binary was stored for this seeded demo document.</div>'}</div>`; openModal('lg'); } catch(e) { toast(e.message,'error'); } };
  window.deleteDemoDocument = function(docId, appId) { document.getElementById('modal-title').textContent = 'Delete document?'; document.getElementById('modal-body').innerHTML = `<p class="text-sm text-muted">This removes the uploaded demo document. You can upload a replacement afterward.</p><div class="flex gap-3 mt-4"><button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button><button class="btn btn-danger" style="flex:1" onclick="runDeleteDocument('${docId}','${appId}')">Delete</button></div>`; openModal(); };
  window.runDeleteDocument = async function(docId, appId) { try { await api('DELETE', `/documents/${docId}`); closeModal(); toast('Document deleted.', 'success'); navigate('application-detail',{applicationId:appId}); } catch(e) { toast(e.message,'error'); } };
  window.showAiUpload = function(appId, requirementId, docType) { document.getElementById('modal-title').textContent = 'Upload document'; document.getElementById('modal-body').innerHTML = `<div class="info-box mb-3">Layered validation (file → content → tamper triage) runs on upload. Passing documents move to <strong>Officer Review</strong>; no automated layer claims government authenticity — the licence officer is the accountable verifier. Address documents named “corrected” demonstrate the resubmission path.</div><div class="form-group"><label>Select file (PDF, JPG, PNG, DOC/DOCX · max 16 MB)</label><input type="file" id="ai-upload-file"></div><div class="flex gap-3"><button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button><button class="btn btn-primary" style="flex:1" onclick="runAiUpload('${appId}','${requirementId||''}','${docType||'OTHER'}')">Upload &amp; validate</button></div>`; openModal(); };
  window.runAiUpload = async function(appId, reqId, docType) { const file = document.getElementById('ai-upload-file')?.files?.[0]; if(!file) { toast('Choose a document first.','warning'); return; } const fd = new FormData(); fd.append('file', file); fd.append('application_id', appId); if(reqId) fd.append('requirement_id', reqId); fd.append('doc_type', docType); try { const d = await apiUpload('/documents/upload', fd); closeModal(); const vs = d.ai_prevalidation.status; const warn = vs === 'RESUBMISSION_REQUIRED' || vs === 'VALIDATION_PENDING'; toast(`Validation: ${vs} (${d.ai_prevalidation.confidence}% confidence).`, warn ? 'warning' : 'success'); navigate('application-detail',{applicationId:appId}); } catch(e) { toast(e.message,'error'); } };
  window.reuseVerifiedDocument = function(appId, reqId, sourceDocId, reqName) { document.getElementById('modal-title').textContent = 'Reuse verified document?'; document.getElementById('modal-body').innerHTML = `<p class="text-sm text-muted">A previously <strong>AI-verified</strong> document from this business already proves <strong>${safe(reqName)}</strong>. Reusing it avoids a re-upload while keeping the verification status (verify once, reuse everywhere).</p><div class="flex gap-3 mt-4"><button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button><button class="btn btn-primary" style="flex:1" onclick="runReuseDocument('${appId}','${reqId}','${sourceDocId}')">↩ Reuse document</button></div>`; openModal(); };
  window.runReuseDocument = async function(appId, reqId, sourceDocId) { try { const d = await api('POST', '/documents/reuse', { application_id: appId, requirement_id: reqId, source_document_id: sourceDocId }); const doc = d.document || {}; closeModal(); toast(`Reused verified document: ${doc.original_filename || 'done'}.`, 'success'); navigate('application-detail',{applicationId:appId}); } catch(e) { toast(e.message,'error'); } };

  /* ============================================================
     LICENCE OFFICER ROLE — realtime client + officer UI
     ============================================================ */
  const OFFICER_ACCOUNTS = [
    ['inspector@demo.com', 'Arjun Singh · Licence Officer / Inspector', 'Demo@1234'],
  ];

  /* --- Live server-push client (EventSource) ------------------ */
  let _es = null;
  let _lastLiveReload = 0;
  window.startRealtime = function () {
    if (!token || typeof EventSource === 'undefined' || _es) return;
    const source = new EventSource(API + '/realtime/stream?token=' + encodeURIComponent(token));
    source.onmessage = function (event) {
      let msg = null;
      try { msg = JSON.parse(event.data); } catch (e) { return; }
      if (!msg || !msg.event) return;
      if (user && user.role === 'OFFICER' && msg.event === 'new_assignment') {
        toast('New application assigned to your desk.', 'info');
      }
      if (msg.event !== 'application_update' && msg.event !== 'document_update') return;
      const modalOpen = !document.getElementById('generic-modal')?.classList.contains('hidden');
      if (modalOpen) return;
      const now = Date.now();
      if (now - _lastLiveReload > 2500 && currentPage && typeof PAGES[currentPage] === 'function') {
        _lastLiveReload = now;
        PAGES[currentPage](window._pageParams || {});
      }
    };
    source.onerror = function () {
      /* EventSource auto-reconnects. If the connection fails repeatedly,
         close and retry after a delay to avoid hammering the server. */
      try { source.close(); } catch(e) {}
      _es = null;
      if (token) { setTimeout(window.startRealtime, 5000); }
    };
    _es = source;
  };
  window.closeRealtime = function () {
    if (_es) { try { _es.close(); } catch (e) { /* noop */ } _es = null; }
  };

  /* --- Officer desk switcher --- */
  window.officerSwitch = async function (select) {
    const email = select?.value;
    if (!email) return;
    const account = OFFICER_ACCOUNTS.find(a => a[0] === email);
    const password = account ? account[2] : 'Demo@1234';
    try {
      const d = await api('POST', '/auth/login', { email, password });
      handleLogin(d.token, d.user);
      toast(`Now at the ${d.user.name} desk.`, 'success');
    } catch (e) { toast(e.message, 'error'); }
  };

  function officerSlaLine(app) {
    if (!app.sla_deadline || ['APPROVED', 'REJECTED'].includes(app.status)) return '<span class="text-xs text-muted">No deadline</span>';
    const days = Math.round((new Date(app.sla_deadline) - new Date()) / 86400000);
    const cls = days < 0 ? 'text-xs" style="color:#dc2626' : days <= 3 ? 'text-xs" style="color:#b45309' : 'text-xs text-muted';
    return `<span class="${cls}">SLA ${days < 0 ? '<b>breached</b> ⏱' : `${days}d remaining`}</span>`;
  }

  function officerAppRows(apps, emptyText) {
    if (!apps || apps.length === 0) {
      return `<div class="card" style="text-align:center;color:var(--slate);padding:32px">${safe(emptyText || 'No applications match.')}</div>`;
    }
    return apps.map(a => `
      <div class="card" style="margin-bottom:10px;cursor:pointer" onclick="navigate('officer-app-detail',{applicationId:'${a.id}'})">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
          <div>
            <div style="font-weight:700">${safe(a.application_number)} · ${safe(a.business_name || a.approval_type_name)}</div>
            <div class="text-sm text-muted">${safe(a.applicant_name)} · ${safe(a.approval_type_name)} · Applied ${fmtDate(a.submission_date)}</div>
          </div>
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
            ${stateBadge(a.status)}
            ${officerSlaLine(a)}
          </div>
        </div>
      </div>`).join('');
  }

  /* --- Officer dashboard --- */
  PAGES['officer-dashboard'] = async function () {
    showLoadingUpgrade();
    try {
      const [me, dash] = await Promise.all([
        api('GET', '/officer/me'),
        api('GET', '/officer/dashboard'),
      ]);
      const officer = me.officer || {};
      const stats = dash.stats || {};
      const by = stats.by_status || {};
      const licences = dash.licences || [];
      const actionables = dash.actionable_applications || [];
      const term = ['APPROVED', 'REJECTED', 'EXPIRED'];
      const statTile = (label, value, color) => `<div class="stat-card"><div class="stat-icon" style="background:#eef2ff;color:${color || 'var(--ink)'};font-size:20px">${value || 0}</div><div class="stat-label">${label}</div></div>`;

      const pendingReview = actionables.filter(a => a.status === 'DECISION_PENDING' && a.ai_reviewed_at);
      const awaitingDocs  = actionables.filter(a => a.status === 'CORRECTION_REQUIRED' || a.status === 'ADDITIONAL_DOCUMENTS_REQUIRED');
      const underInsp     = actionables.filter(a => a.status === 'INSPECTION_SCHEDULED' || a.status === 'INSPECTION_STARTED');
      const finalApproval = actionables.filter(a => a.status === 'INSPECTION_COMPLETED' || a.status === 'INSPECTION_PASSED');
      const completed     = actionables.filter(a => term.includes(a.status));

      document.getElementById('page-content').innerHTML = `
        <div class="mb-4">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
            <div>
              <h2 style="font-size:18px;font-weight:800;margin:0">🏛️ Licence Officer / Inspector Desk</h2>
              <div class="text-sm text-muted">${safe(officer.designation)} · ${safe(officer.authority)} · ${safe(officer.location)}, ${safe(officer.state)}</div>
              <div class="text-xs text-muted" style="margin-top:2px">Officer ID ${safe(officer.officer_number)} · ${safe(officer.email)}</div>
            </div>
          </div>
          ${demoNotice(true)}
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px">
          ${statTile('Action Required', stats.actionable || 0, '#1d4ed8')}
          ${statTile('Awaiting Documents', stats.awaiting_documents || 0, '#b45309')}
          ${statTile('Under Inspection', stats.under_inspection || 0, '#6d28d9')}
          ${statTile('Completed', stats.completed || 0, '#047857')}
        </div>

        <div class="card mb-4" style="padding:0;overflow:hidden">
          <div style="padding:14px 18px;border-bottom:1px solid var(--line,#e2e8f0)">
            <strong style="font-weight:800">ACTION REQUIRED</strong>
            <span class="badge badge-blue" style="margin-left:8px">${pendingReview.length} Pending Review</span>
            ${finalApproval.length ? `<span class="badge badge-green" style="margin-left:6px">${finalApproval.length} Final Approval Ready</span>` : ''}
          </div>
          <div style="padding:8px">
            ${pendingReview.length || finalApproval.length ? officerAppRows([...pendingReview, ...finalApproval], '') : '<div class="text-sm text-muted" style="padding:12px">No action required at this time.</div>'}
          </div>
        </div>

        <div class="card mb-4" style="padding:0;overflow:hidden">
          <div style="padding:14px 18px;border-bottom:1px solid var(--line,#e2e8f0)">
            <strong style="font-weight:800">AWAITING DOCUMENTS</strong>
            <span class="badge badge-amber" style="margin-left:8px">${awaitingDocs.length}</span>
          </div>
          <div style="padding:8px">
            ${awaitingDocs.length ? officerAppRows(awaitingDocs, '') : '<div class="text-sm text-muted" style="padding:12px">No applications awaiting documents.</div>'}
          </div>
        </div>

        <div class="card mb-4" style="padding:0;overflow:hidden">
          <div style="padding:14px 18px;border-bottom:1px solid var(--line,#e2e8f0)">
            <strong style="font-weight:800">UNDER INSPECTION</strong>
            <span class="badge badge-purple" style="margin-left:8px">${underInsp.length}</span>
          </div>
          <div style="padding:8px">
            ${underInsp.length ? officerAppRows(underInsp, '') : '<div class="text-sm text-muted" style="padding:12px">No inspections currently underway.</div>'}
          </div>
        </div>

        <div style="margin-top:16px;text-align:right">
          <button class="btn btn-outline btn-sm" onclick="navigate('officer-inbox')">Open full inbox →</button>
        </div>`;
    } catch (e) { showError('Failed to load officer dashboard: ' + e.message); }
  };

  /* --- Officer inbox --- */
  const OFFICER_FILTERS = [
    ['', 'All'],
    ['DECISION_PENDING,INSPECTION_PASSED', '⚡ Decide now'],
    ['INSPECTION_REQUIRED,INSPECTION_SCHEDULED,INSPECTION_COMPLETED', '🔍 Inspection'],
    ['ADDITIONAL_DOCUMENTS_REQUIRED,CORRECTION_REQUIRED', '📄 Awaiting docs'],
    ['SUBMITTED,UNDER_REVIEW,DOCUMENT_VALIDATION', '⏳ In pipeline'],
    ['APPROVED,REJECTED', '✅ Decided'],
  ];
  window.officerInboxGo = function () {
    const status = document.getElementById('officer-inbox-status')?.value || '';
    const search = document.getElementById('officer-inbox-search')?.value || '';
    navigate('officer-inbox', { status, search });
  };
  PAGES['officer-inbox'] = async function (params) {
    params = params || {};
    showLoadingUpgrade();
    try {
      const status = (params.status || '').toString() || '';
      const search = (params.search || '').toString() || '';
      const licence = (params.licence || '').toString() || '';
      const qs = new URLSearchParams();
      if (status) qs.set('status', status);
      if (licence) qs.set('licence', licence);
      if (search) qs.set('search', search);
      const me = await api('GET', '/officer/me');
      const officer = me.officer || {};
      const d = await api('GET', '/officer/applications?' + qs.toString());
      const apps = d.applications || [];
      document.getElementById('page-content').innerHTML = `
        <div class="mb-4">
          <h2 style="font-size:18px;font-weight:800;margin:0">📥 Applications Inbox</h2>
          <div class="text-sm text-muted">${safe(officer.designation)} — only applications routed to your desk are visible (${apps.length} shown)</div>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;align-items:center">
          <select id="officer-inbox-status" style="width:220px">
            ${OFFICER_FILTERS.map(([val, label]) => `<option value="${val}" ${val === status ? 'selected' : ''}>${safe(label)}</option>`).join('')}
          </select>
          <input id="officer-inbox-search" placeholder="Search number / business / applicant…" value="${safe(search)}" style="flex:1;min-width:200px" onkeydown="if(event.key==='Enter')officerInboxGo()">
          <button class="btn btn-outline btn-sm" onclick="officerInboxGo()">Apply</button>
        </div>
        <div class="mb-4">${officerAppRows(apps, 'No applications match this view yet.')}</div>`;
    } catch (e) { showError('Failed to load officer inbox: ' + e.message); }
  };

  /* --- Officer application detail + decision actions --- */
  function officerActionButtons(app, actions) {
    const decided = app.status === 'APPROVED' || app.status === 'REJECTED';
    return `
      <div class="mt-4">
        <h3 style="font-size:15px;font-weight:800;margin:0 0 10px">Officer decision</h3>
        ${decided ? `<div class="info-box">This application is already decided (${safe(app.status)}). Decided records are retained as an audit trail.</div>` : ''}
        ${!decided ? `<div style="display:flex;gap:10px;flex-wrap:wrap">
          ${actions.can_pass_inspection ? `<button class="btn btn-primary" onclick="officerPassInspection('${app.id}')">✅ Pass Inspection</button>` : ''}
          ${actions.can_decide ? `<button class="btn btn-primary" onclick="officerApprove('${app.id}')">✓ Approve</button>
            <button class="btn btn-danger" onclick="officerReject('${app.id}')">✕ Reject</button>` : ''}
          ${actions.can_request_documents ? `<button class="btn btn-outline" onclick="officerRequestDocs('${app.id}')">📄 Request documents</button>` : ''}
          ${actions.can_require_inspection ? `<button class="btn btn-outline" onclick="officerRequireInspection('${app.id}')">🔍 Require inspection</button>` : ''}
        </div>` : ''}
        ${app.status === 'ADDITIONAL_DOCUMENTS_REQUIRED' ? '<div class="warning-box mt-3">Applicant must resubmit before you can decide.</div>' : ''}
        ${app.status === 'CORRECTION_REQUIRED' ? '<div class="warning-box mt-3">Awaiting applicant correction — the applicant must upload corrected documents and resubmit.</div>' : ''}
        ${app.status === 'INSPECTION_REQUIRED' || app.status === 'INSPECTION_SCHEDULED' ? '<div class="warning-box mt-3">Physical inspection pending — approval unlocks after a PASS report.</div>' : ''}
      </div>`;
  }

  function officerDecisionModal(title, appId, action, placeholder) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = `
      <p class="text-sm text-muted">Recorded in the audit trail and pushed live to the applicant. This is a simulated officer decision for the SIH demo.</p>
      <div class="form-group"><label>Decision reason (required)</label>
        <textarea id="officer-decision-reason" rows="3" placeholder="${safe(placeholder)}"></textarea></div>
      <div class="flex gap-3 mt-4">
        <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
        <button class="btn ${action === 'reject' ? 'btn-danger' : 'btn-primary'}" style="flex:1" onclick="officerDecisionSubmit('${appId}','${action}')">${action === 'reject' ? '✕ Reject' : '✓ Approve'}</button>
      </div>`;
    openModal();
  }
  window.officerDecisionSubmit = async function (appId, action) {
    const reason = document.getElementById('officer-decision-reason')?.value?.trim();
    if (!reason) { toast('A decision reason is required.', 'warning'); return; }
    try {
      const d = await api('POST', `/officer/applications/${appId}/${action}`, { reason });
      closeModal();
      const cert = d.certificate;
      toast(action === 'approve' ? (cert ? `Approved — certificate ${cert.certificate_number} issued.` : 'Approved.') : 'Application rejected.', action === 'approve' ? 'success' : 'warning');
      navigate('officer-inbox', { status: 'DECISION_PENDING,INSPECTION_COMPLETED' });
    } catch (e) { toast(e.message === 'Bad request' ? 'The application cannot be decided in its current state.' : e.message, 'error'); }
  };
  window.officerApprove = function (appId) { officerDecisionModal('Approve application', appId, 'approve', 'e.g. Documents verified, fees borne by the scheme, premises comply.'); };
  window.officerReject = function (appId) { officerDecisionModal('Reject application', appId, 'reject', 'e.g. Premises do not meet the regulatory criteria.'); };
  window.officerPassInspection = function (appId) {
    document.getElementById('modal-title').textContent = '✅ Pass Inspection';
    document.getElementById('modal-body').innerHTML = `
      <p class="text-sm text-muted">The inspection for this application has returned a PASS result. Confirm that the inspection outcome is accepted and the application may proceed to final approval.</p>
      <div class="form-group"><label>Notes (optional)</label>
        <textarea id="officer-pass-notes" rows="3" placeholder="e.g. Inspection report reviewed, all requirements met."></textarea></div>
      <div class="flex gap-3 mt-4">
        <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" style="flex:1" onclick="officerPassInspectionSubmit('${appId}')">✅ Confirm passed</button>
      </div>`;
    openModal();
  };
  window.officerPassInspectionSubmit = async function (appId) {
    const notes = document.getElementById('officer-pass-notes')?.value?.trim() || '';
    try {
      await api('POST', `/officer/applications/${appId}/pass-inspection`, { notes });
      closeModal();
      toast('Inspection confirmed passed. Application now ready for final approval.', 'success');
      navigate('officer-inbox', { status: 'DECISION_PENDING,INSPECTION_COMPLETED,INSPECTION_PASSED' });
    } catch (e) { toast(e.message === 'Bad request' ? 'Cannot confirm inspection in current state.' : e.message, 'error'); }
  };
  window.officerRequestDocs = function (appId) {
    document.getElementById('modal-title').textContent = 'Request additional documents';
    document.getElementById('modal-body').innerHTML = `
      <p class="text-sm text-muted">The applicant is notified in real time and can resubmit once the requested documents are uploaded.</p>
      <div class="form-group"><label>Which documents are required?</label>
        <textarea id="officer-doc-notes" rows="3" placeholder="e.g. Fresh bank statement, updated layout plan, GST returns…"></textarea></div>
      <div class="flex gap-3 mt-4">
        <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" style="flex:1" onclick="officerRequestDocsSubmit('${appId}')">Send request</button>
      </div>`;
    openModal();
  };
  window.officerRequestDocsSubmit = async function (appId) {
    const notes = document.getElementById('officer-doc-notes')?.value?.trim();
    if (!notes) { toast('Describe the documents required.', 'warning'); return; }
    try {
      await api('POST', `/officer/applications/${appId}/request-documents`, { notes });
      closeModal();
      toast('Document request sent to the applicant (live push).', 'success');
      navigate('officer-inbox');
    } catch (e) { toast(e.message, 'error'); }
  };
  window.officerRequireInspection = function (appId) {
    document.getElementById('modal-title').textContent = 'Require physical inspection';
    document.getElementById('modal-body').innerHTML = `
      <p class="text-sm text-muted">An inspector is auto-assigned (least-busy). The application cannot be approved until the report returns PASS. Simulated inspection report — SIH demo.</p>
      <div class="flex gap-3 mt-4">
        <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" style="flex:1" onclick="officerRequireInspectionSubmit('${appId}')">Schedule inspection</button>
      </div>`;
    openModal();
  };
  window.officerRequireInspectionSubmit = async function (appId) {
    try {
      await api('POST', `/officer/applications/${appId}/require-inspection`, {});
      closeModal();
      toast('Inspection scheduled — inspector notified.', 'success');
      navigate('officer-inbox');
    } catch (e) { toast(e.message, 'error'); }
  };

  window.officerDocReview = function (docId, action, appId) {
    const approving = action === 'approve';
    const resubmitting = action === 'resubmit';
    document.getElementById('modal-title').textContent = approving ? 'Approve document' : (resubmitting ? 'Request document resubmission' : 'Reject document');
    document.getElementById('modal-body').innerHTML = `
      <p class="text-sm text-muted">${approving
        ? 'Mark <strong>this individual document</strong> as verified. Each document is decided independently — other documents are unaffected.'
        : resubmitting
        ? 'Keep the application open and ask the applicant to <strong>upload a corrected version of this individual document</strong>.'
        : 'The applicant is notified <strong>in real time</strong> with the exact reason and can replace the document.'}</p>
      ${approving ? '' : `<div class="form-group"><label>Reason (required)</label>
        <textarea id="officer-doc-reason" rows="3" placeholder="${resubmitting ? 'e.g. Upload a corrected version with the updated address.' : 'e.g. Address proof mismatch — please upload a corrected document.'}"></textarea></div>`}
      <div class="flex gap-3 mt-4">
        <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
        <button class="btn ${approving ? 'btn-success' : resubmitting ? 'btn-amber' : 'btn-danger'}" style="flex:1" onclick="officerDocReviewSubmit('${docId}','${action}','${appId}')">${approving ? '✓ Approve document' : resubmitting ? '↻ Request resubmission' : '✕ Reject document'}</button>
      </div>`;
    openModal();
  };
  window.officerDocReviewSubmit = async function (docId, action, appId) {
    const approving = action === 'approve';
    const resubmitting = action === 'resubmit';
    const reason = document.getElementById('officer-doc-reason')?.value?.trim() || '';
    if (!approving && !reason) { toast('Provide the reason for the applicant.', 'warning'); return; }
    try {
      const body = approving
        ? { status: 'APPROVED', notes: 'Document individually reviewed and approved by the licensing officer.' }
        : resubmitting
        ? { status: 'RESUBMISSION_REQUIRED', rejection_reason: reason, notes: 'Officer requested a corrected document.' }
        : { status: 'REJECTED', rejection_reason: reason };
      await api('POST', `/documents/${docId}/verify`, body);
      closeModal();
      toast(approving
        ? 'Document approved — recorded to the audit trail.'
        : 'Applicant notified in real time; document marked for resubmission/rejection.', 'success');
      if (appId) navigate('officer-app-detail', { applicationId: appId });
    } catch (e) { toast(e.message, 'error'); }
  };

  PAGES['officer-app-detail'] = async function (params) {
    const appId = params.applicationId || (window._pageParams || {}).applicationId;
    if (!appId) { showError('Missing application id.'); return; }
    showLoadingUpgrade();
    try {
      const d = await api('GET', `/officer/applications/${appId}`);
      const app = d.application;
      const actions = app.officer_actions || {};
      const docs = app.documents || [];
      const inspections = app.inspections || [];
      const timeline = (app.status_history || []).slice().reverse();
      const cert = app.certificate;
      document.getElementById('page-content').innerHTML = `
        <div class="mb-4">
          <button class="btn btn-outline btn-sm" onclick="navigate('officer-inbox')">← Back to inbox</button>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
          <div>
            <h2 style="font-size:18px;font-weight:800;margin:0">${safe(app.application_number)} · ${safe(app.approval_type_name)}</h2>
            <div class="text-sm text-muted">${safe(app.business_name)} · ${safe(app.applicant_name)} · ${safe(app.department_name)}</div>
          </div>
          <div>${stateBadge(app.status)} ${app.risk_level ? riskBadge(app.risk_level) : ''}</div>
        </div>
        ${demoNotice(true)}
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0">
          <div class="card"><div class="text-sm text-muted">Submitted</div><div>${fmtDate(app.submission_date)}</div></div>
          <div class="card"><div class="text-sm text-muted">SLA deadline</div><div>${fmtDate(app.sla_deadline)}</div></div>
          <div class="card"><div class="text-sm text-muted">Risk</div><div>${safe(app.risk_level || '—')} (${app.risk_score || '—'})</div></div>
          <div class="card"><div class="text-sm text-muted">AI review</div><div>${app.ai_reviewed_at ? '✅ Passed gate' : '⏳ Not yet run'}</div></div>
        </div>
        <div class="card mb-4">
          <h3 style="font-size:15px;font-weight:800;margin:0 0 8px">🤖 AI Compliance summary</h3>
          ${app.ai_decision_summary ? `<div class="text-sm">${safe(app.ai_decision_summary)}</div>` : '<div class="text-sm text-muted">No assessment has run yet.</div>'}
          ${app.ai_decision ? `<div class="text-xs text-muted mt-2">Decision flag: ${stateBadge(app.ai_decision)} (${safe(app.ai_decision_confidence)}% confidence)</div>` : ''}
          ${app.correction_notes ? `<div class="warning-box mt-3">${safe(app.correction_notes)}</div>` : ''}
        </div>
        <div class="card mb-4">
          <h3 style="font-size:15px;font-weight:800;margin:0 0 8px">📎 Documents</h3>
          ${docs.length ? docs.map(doc => {
            const dl = String(doc.verification_status || 'PENDING').toUpperCase();
            const reviewed = dl === 'APPROVED' || dl === 'VERIFIED' || dl === 'REJECTED' || dl === 'RESUBMISSION_REQUIRED';
            // Per-document accountability: the officer independently approves,
            // rejects or requests resubmission of each document — deciding one
            // document NEVER decides the others.
            return `<div style="padding:10px 0;border-bottom:1px solid var(--line,#e2e8f0)">
              <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
                <div><div style="font-weight:600;font-size:14px">${safe(doc.requirement_name || doc.doc_type || 'Document')}${doc.document_version > 1 ? ` <span class="badge badge-slate">v${safe(doc.document_version)}</span>` : ''}</div>
                <div class="text-xs text-muted">${safe(doc.original_filename || doc.filename || doc.status || '')}${doc.verified_by_name ? ' · reviewed by ' + safe(doc.verified_by_name) : ''}</div>
                ${doc.rejection_reason ? `<div class="text-xs mt-1" style="color:#dc2626"><strong>Reason:</strong> ${safe(doc.rejection_reason)}</div>` : ''}</div>
                <div style="text-align:right">
                  ${stateBadge(doc.verification_status)}
                  <div class="flex gap-2 mt-2">
                    <button class="btn btn-outline btn-sm" onclick="previewDocument('${doc.id}')">View</button>
                    ${!reviewed ? `<button class="btn btn-success btn-sm" onclick="officerDocReview('${doc.id}','approve','${appId}')">✓ Approve</button><button class="btn btn-danger btn-sm" onclick="officerDocReview('${doc.id}','reject','${appId}')">✕ Reject</button><button class="btn btn-amber btn-sm" onclick="officerDocReview('${doc.id}','resubmit','${appId}')">↻ Resubmit</button>` : ''}
                  </div>
                </div>
              </div>
            </div>`;
          }).join('') : '<div class="text-sm text-muted">No documents uploaded yet.</div>'}
        </div>
        <div class="card mb-4">
          <h3 style="font-size:15px;font-weight:800;margin:0 0 8px">🔍 Inspections</h3>
          ${inspections.length ? inspections.map(ins => `<div style="padding:8px 0;border-bottom:1px solid var(--line,#e2e8f0)">
            <div style="display:flex;justify-content:space-between;gap:10px">
              <div><span style="font-weight:600">${safe(ins.inspector_name)}</span> <span class="text-sm text-muted">· ${safe(ins.scheduled_date || 'assigned')}</span></div>
              <div>${stateBadge(ins.status)} ${ins.overall_result ? stateBadge(ins.overall_result) : ''}</div>
            </div>
            ${ins.notes ? `<div class="text-sm text-muted mt-1">${safe(ins.notes)}</div>` : ''}
          </div>`).join('') : '<div class="text-sm text-muted">No inspections for this application.</div>'}
        </div>
        ${cert ? `<div class="card mb-4"><h3 style="font-size:15px;font-weight:800;margin:0 0 8px">🏅 Certificate</h3>
          <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">
            <div><span style="font-weight:700">${safe(cert.certificate_number)}</span>
            <div class="text-sm text-muted">Issued ${fmtDate(cert.issue_date)} · Valid until ${fmtDate(cert.valid_until)} · ${safe(cert.verification_id)}</div></div>
          </div></div>` : ''}
        ${officerActionButtons(app, actions)}
        <div class="card mt-4">
          <h3 style="font-size:15px;font-weight:800;margin:0 0 8px">📜 Audit trail</h3>
          ${timeline.length ? timeline.map(h => `<div style="padding:6px 0;border-bottom:1px solid var(--line,#e2e8f0);display:flex;justify-content:space-between;gap:10px">
            <div class="text-sm">${stateBadge(h.status)} ${actorTag(h.changed_by_name)} <span class="text-muted">${safe(h.notes || '')}</span></div>
            <div class="text-xs text-muted" style="flex-shrink:0">${safe(h.changed_by_name||'System')} · ${fmtDateTime(h.changed_at)}</div></div>`).join('') : '<div class="text-sm text-muted">No status history yet.</div>'}
        </div>`;
    } catch (e) { showError('Failed to load officer application: ' + e.message); }
  };

  /* Re-render a persisted session with the upgraded navigation and start the
     live realtime stream. Applied for every role so the applicant, officer,
     inspector and admin all get the upgraded nav + live pushes on reload. */
  if (user && token) {
    if (typeof window.showApp === 'function') window.showApp();
    if (typeof window.startRealtime === 'function') window.startRealtime();
  }
})();
