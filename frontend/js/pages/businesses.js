// =============================================
//  NIRMAN — My Businesses Page
//  File: frontend/js/pages/businesses.js
// =============================================

PAGES['businesses'] = async function () {
  try {
    const d    = await api('GET', '/businesses/');
    const bizs = d.businesses || [];

    const listHTML = bizs.length === 0
      ? `<div class="card" style="text-align:center;padding:64px">
           <div style="font-size:52px;margin-bottom:16px">🏢</div>
           <div style="font-size:18px;font-weight:700;margin-bottom:8px">No Businesses Registered</div>
           <p class="text-muted mb-4">Register your first business to get your approval checklist</p>
           <button class="btn btn-primary" onclick="navigate('create-business')">Register Your First Business</button>
         </div>`
      : bizs.map(b => {
          const pendingTotal = (b.pending || 0) + (b.corrections || 0);
          return `
            <div class="biz-card" onclick="navigate('business-detail',{businessId:'${b.id}'})">
              <!-- Left: Icon -->
              <div class="biz-icon">${sectorIcon(b.sector)}</div>

              <!-- Centre: Info -->
              <div class="biz-info">
                <div class="biz-name">${b.name}</div>
                <div class="biz-meta">${(b.business_type || '').replace(/_/g,' ')} · ${b.sector || ''}</div>
                <div class="biz-sub">
                  📍 ${[b.city, b.state].filter(Boolean).join(', ')}
                  &nbsp;·&nbsp; 👥 ${b.employee_count || 0} employees
                  &nbsp;·&nbsp; ₹${((b.investment_amount || 0) / 100000).toFixed(1)}L investment
                </div>
              </div>

              <!-- Right: Stats -->
              <div class="biz-stats">
                <div class="biz-stat">
                  <div class="biz-stat-num">${b.total_approvals || 0}</div>
                  <div class="biz-stat-label text-muted">Total</div>
                </div>
                <div class="biz-stat">
                  <div class="biz-stat-num text-green">${b.approved || 0}</div>
                  <div class="biz-stat-label" style="color:var(--green)">Approved</div>
                </div>
                <div class="biz-stat">
                  <div class="biz-stat-num text-amber">${pendingTotal}</div>
                  <div class="biz-stat-label" style="color:var(--amber)">Pending</div>
                </div>
                <div class="biz-stat">
                  <div class="biz-stat-num" style="color:var(--red)">${b.pending_documents || 0}</div>
                  <div class="biz-stat-label" style="color:var(--red)">Docs to Apply</div>
                </div>
                <div class="biz-arrow">→</div>
              </div>
            </div>`;
        }).join('');

    document.getElementById('page-content').innerHTML = `
      <div class="flex justify-between items-center mb-4">
        <div>
          <div class="page-title">My Businesses</div>
          <div class="page-subtitle">${bizs.length} business(es) registered</div>
        </div>
        <button class="btn btn-primary" onclick="navigate('create-business')">+ Register Business</button>
      </div>
      ${listHTML}
    `;
  } catch (e) {
    showError(e.message);
  }
};

// =============================================
//  Business Detail Page
// =============================================

PAGES['business-detail'] = async function (params) {
  const id = (params || {}).businessId || window._pageParams?.businessId;
  try {
    const [bd, cd] = await Promise.all([
      api('GET', `/businesses/${id}`),
      api('GET', `/businesses/${id}/checklist`),
    ]);
    const b  = bd.business;
    const cl = cd.checklist || [];
    const approved = cl.filter(i => i.application_status === 'APPROVED').length;
    const pct      = cl.length ? Math.round((approved / cl.length) * 100) : 0;

    window._currentBizId = id;

    const progressRows = [
      ['Approved',   cl.filter(i => i.application_status === 'APPROVED').length,                   '#f0fdf4','var(--green)'],
      ['In Progress',cl.filter(i => ['SUBMITTED','UNDER_REVIEW','INSPECTION_REQUIRED','INSPECTION_SCHEDULED','INSPECTION_COMPLETED','DECISION_PENDING'].includes(i.application_status)).length,'#eff6ff','var(--blue)'],
      ['Needs Action',cl.filter(i => ['DRAFT','CORRECTION_REQUIRED'].includes(i.application_status)).length,'#fffbeb','var(--amber)'],
      ['Not Applied', cl.filter(i => i.application_status === 'NOT_APPLIED').length,               '#f8fafc','var(--slate)'],
      ['Docs to Apply', b.pending_documents || 0,                                                   '#fef2f2','var(--red)'],
    ];

    document.getElementById('page-content').innerHTML = `
      <!-- Page Header with Back Button -->
      <div class="flex items-start gap-3 mb-4">
        <button class="btn btn-outline btn-sm btn-icon" onclick="goBack()" title="Go back" style="margin-top:4px">←</button>
        <div>
          <div class="flex items-center gap-3 flex-wrap">
            <div class="page-title">${b.name}</div>
            <span class="badge badge-green">Active</span>
            <span class="demo-badge">DEMO</span>
          </div>
          <div class="text-muted">${(b.business_type || '').replace(/_/g,' ')} · ${b.sector || ''} · ${b.city || ''}, ${b.state || ''}</div>
          <div class="text-xs text-muted mt-1">
            Reg: ${b.registration_number || '—'} &nbsp;·&nbsp;
            ${b.employee_count || 0} employees &nbsp;·&nbsp;
            ₹${((b.investment_amount || 0) / 100000).toFixed(1)}L investment
          </div>
        </div>
      </div>

      <!-- Progress Card -->
      <div class="card mb-4">
        <div class="flex justify-between items-center mb-3">
          <div style="font-size:16px;font-weight:700">Approval Progress</div>
          <div class="text-muted">${approved} of ${cl.length} completed</div>
        </div>
        <div class="progress-track" style="height:10px;margin-bottom:16px">
          <div class="progress-fill" style="width:${pct}%"></div>
        </div>
        <div class="grid-5" style="gap:8px">
          ${progressRows.map(([label, count, bg, color]) => `
            <div style="background:${bg};border-radius:10px;padding:12px;text-align:center">
              <div style="font-size:22px;font-weight:800;color:${color}">${count}</div>
              <div style="font-size:12px;font-weight:600;color:${color}">${label}</div>
            </div>`).join('')}
        </div>
      </div>

      <!-- Checklist -->
      <div style="font-size:16px;font-weight:700;margin-bottom:12px">Approval Checklist</div>
      ${cl.map((item, i) => {
          const at             = item.approval_type || {};
          const status         = item.application_status || 'NOT_APPLIED';
          const isApproved     = status === 'APPROVED';
          const isNotApplied   = status === 'NOT_APPLIED';
          const isDraft        = status === 'DRAFT';
          const needsCorrection= status === 'CORRECTION_REQUIRED';
          return `
            <div class="checklist-item ${isApproved ? 'approved' : (needsCorrection || isDraft ? 'needs-action' : '')}">
              <div class="checklist-num ${isApproved ? 'approved' : ''}">${isApproved ? '✓' : i + 1}</div>
              <div style="flex:1;min-width:0">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <div style="font-size:14px;font-weight:700">${at.name || 'Approval'}</div>
                  ${badge(status)}
                  ${at.requires_inspection && !isApproved ? '<span class="badge badge-amber">🔍 Inspection</span>' : ''}
                </div>
                <div class="text-xs text-muted">
                  ${at.department?.name || ''} · Est. ${at.estimated_days || '?'} days · ${at.document_requirements?.length || 0} docs required
                </div>
                ${item.application_number ? `<div class="text-xs mt-1 text-blue">App: ${item.application_number}</div>` : ''}
              </div>
              <div class="flex flex-col gap-2 flex-shrink-0" style="margin-left:12px">
                ${isNotApplied
                  ? `<button class="btn btn-primary btn-sm" onclick="startApplication('${at.id}','${id}')">Start →</button>`
                  : ''}
                ${(isDraft || needsCorrection) && item.application_id
                  ? `<button class="btn btn-amber btn-sm" onclick="navigate('application-detail',{applicationId:'${item.application_id}'})">Continue →</button>`
                  : ''}
                ${!isNotApplied && !isDraft && !needsCorrection && item.application_id
                  ? `<button class="btn btn-outline btn-sm" onclick="navigate('application-detail',{applicationId:'${item.application_id}'})">View</button>`
                  : ''}
              </div>
            </div>`;
        }).join('')}
    `;
  } catch (e) {
    showError(e.message);
  }
};

/* Start a new application for a given approval type */
window.startApplication = async function (approvalTypeId, businessId) {
  try {
    const d = await api('POST', '/applications/', {
      business_id:      businessId || window._currentBizId,
      approval_type_id: approvalTypeId,
    });
    toast('Application created!', 'success');
    navigate('application-detail', { applicationId: d.application.id });
  } catch (e) {
    toast(e.message.includes('already') ? 'An application already exists for this approval type.' : e.message,
      e.message.includes('already') ? 'warning' : 'error');
  }
};
