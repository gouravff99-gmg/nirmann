// =============================================
//  NIRMAN — Dashboard Page
//  File: frontend/js/pages/dashboard.js
// =============================================

PAGES['dashboard'] = async function () {
  try {
    const d    = await api('GET', '/businesses/');
    const bizs = d.businesses || [];

    const totalApprovals = bizs.reduce((s, b) => s + (b.total_approvals || 0), 0);
    const approved       = bizs.reduce((s, b) => s + (b.approved || 0), 0);
    const pending        = bizs.reduce((s, b) => s + (b.pending || 0), 0);
    const corrections    = bizs.reduce((s, b) => s + (b.corrections || 0), 0);

    // Business grid cards
    const biz_html = bizs.length === 0
      ? `<div class="card" style="text-align:center;padding:60px">
           <div style="font-size:48px;margin-bottom:16px">🏢</div>
           <div style="font-size:17px;font-weight:700;margin-bottom:8px">No Businesses Yet</div>
           <p class="text-muted mb-4">Register your first business to get started</p>
           <button class="btn btn-primary" onclick="navigate('create-business')">+ Register Business</button>
         </div>`
      : `<div class="grid-3">
           ${bizs.map(b => {
               const pct = b.total_approvals ? Math.round((b.approved / b.total_approvals) * 100) : 0;
               return `
                 <div class="card card-hover" onclick="navigate('business-detail',{businessId:'${b.id}'})">
                   <div class="flex justify-between items-start mb-4">
                     <div class="min-w-0">
                       <div style="font-size:15px;font-weight:700;margin-bottom:4px">${b.name}</div>
                       <div class="text-muted">${(b.business_type || '').replace(/_/g,' ')}</div>
                       <div class="text-xs text-muted mt-1">${b.city || ''}, ${b.state || ''}</div>
                     </div>
                     <div style="font-size:28px;flex-shrink:0;margin-left:8px">${sectorIcon(b.sector)}</div>
                   </div>
                   <div class="grid-3" style="gap:8px;margin-bottom:12px">
                     <div style="background:#f8fafc;border-radius:8px;padding:10px;text-align:center">
                       <div style="font-size:20px;font-weight:800">${b.total_approvals || 0}</div>
                       <div class="text-xs text-muted">Total</div>
                     </div>
                     <div style="background:#f0fdf4;border-radius:8px;padding:10px;text-align:center">
                       <div style="font-size:20px;font-weight:800;color:var(--green)">${b.approved || 0}</div>
                       <div class="text-xs" style="color:var(--green)">Done</div>
                     </div>
                     <div style="background:#fffbeb;border-radius:8px;padding:10px;text-align:center">
                       <div style="font-size:20px;font-weight:800;color:var(--amber)">${(b.pending || 0) + (b.corrections || 0)}</div>
                       <div class="text-xs" style="color:var(--amber)">Pending</div>
                     </div>
                   </div>
                   <div class="progress-track">
                     <div class="progress-fill" style="width:${pct}%"></div>
                   </div>
                   <div class="flex justify-between mt-2">
                     <span class="text-xs text-muted">${pct}% complete</span>
                     <span class="text-xs" style="color:var(--blue);font-weight:600">View details →</span>
                   </div>
                 </div>`;
             }).join('')}
         </div>`;

    document.getElementById('page-content').innerHTML = `
      <div class="page-title">Dashboard</div>
      <div class="page-subtitle">Welcome back, ${nirmanState.user.name} 👋</div>

      <div class="grid-4 mb-4">
        <div class="stat-card">
          <div class="stat-icon" style="background:#dbeafe">📋</div>
          <div class="stat-value">${totalApprovals}</div>
          <div class="stat-label">Total Approvals</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:#dcfce7">✅</div>
          <div class="stat-value">${approved}</div>
          <div class="stat-label">Approved</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:#dbeafe">⏳</div>
          <div class="stat-value">${pending}</div>
          <div class="stat-label">In Progress</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:#fef3c7">⚠️</div>
          <div class="stat-value">${corrections}</div>
          <div class="stat-label">Need Action</div>
        </div>
      </div>

      <div class="flex justify-between items-center mb-4">
        <div style="font-size:17px;font-weight:700">My Businesses</div>
        <button class="btn btn-primary btn-sm" onclick="navigate('create-business')">+ Register Business</button>
      </div>

      ${biz_html}
    `;
  } catch (e) {
    showError(e.message);
  }
};
