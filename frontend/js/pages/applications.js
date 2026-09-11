// =============================================
//  NIRMAN — Applications Pages
//  File: frontend/js/pages/applications.js
// =============================================

// ── Applications List ──
PAGES['applications'] = async function () {
  try {
    const d    = await api('GET', '/applications/');
    const apps = d.applications || [];

    document.getElementById('page-content').innerHTML = `
      <div class="page-title">Applications</div>
      <div class="page-subtitle">${apps.length} applications tracked</div>

      <div class="card" style="padding:0;overflow:hidden">
        ${apps.length === 0
          ? '<div style="text-align:center;padding:64px;color:var(--slate)">No applications yet. Register a business and start applying!</div>'
          : `<div class="table-wrap"><table>
               <thead>
                 <tr>
                   <th>App No.</th><th>Approval Type</th><th>Business</th>
                   <th>Status</th><th>Submitted</th><th>SLA</th><th></th>
                 </tr>
               </thead>
               <tbody>
                 ${apps.map(a => `
                   <tr>
                     <td><strong>${a.application_number || '—'}</strong></td>
                     <td>${a.approval_type_name || '—'}</td>
                     <td>${a.business_name || '—'}</td>
                     <td>${badge(a.status)}</td>
                     <td class="text-muted">${a.submission_date ? fmtDate(a.submission_date) : 'Draft'}</td>
                     <td class="${a.sla_deadline && new Date(a.sla_deadline) < new Date() ? 'text-red' : 'text-muted'}">
                       ${fmtDate(a.sla_deadline)}
                     </td>
                     <td>
                       <button class="btn btn-outline btn-sm" onclick="navigate('application-detail',{applicationId:'${a.id}'})">View →</button>
                     </td>
                   </tr>`).join('')}
               </tbody>
             </table></div>`}
      </div>`;
  } catch (e) {
    showError(e.message);
  }
};

// ── Application Detail ──
PAGES['application-detail'] = async function (params) {
  const id = (params || {}).applicationId || window._pageParams?.applicationId;
  try {
    const [ad, dd] = await Promise.all([
      api('GET', `/applications/${id}`),
      api('GET', `/documents/application/${id}`),
    ]);
    const app  = ad.application;
    const reqs = dd.requirements || [];
    const docs = dd.documents    || [];

    const canSubmit  = app.status === 'DRAFT'               && nirmanState.user.role === 'APPLICANT';
    const canCorrect = app.status === 'CORRECTION_REQUIRED' && nirmanState.user.role === 'APPLICANT';

    // Journey step index
    const journeySteps = ['Application','Documents','Review','Inspection','Decision'];
    const stepIdx =
      app.status === 'DRAFT'      ? 0 :
      app.status === 'SUBMITTED'  ? 1 :
      ['UNDER_REVIEW','CORRECTION_REQUIRED','DECISION_PENDING'].includes(app.status) ? 2 :
      ['INSPECTION_REQUIRED','INSPECTION_SCHEDULED','INSPECTION_COMPLETED'].includes(app.status) ? 3 :
      ['APPROVED','REJECTED'].includes(app.status) ? 4 : 0;

    const journeyHTML = journeySteps.map((s, i) => `
      <div class="flex items-center" style="flex-shrink:0">
        <div class="step-col">
          <div class="step-circle ${i < stepIdx ? 'done' : i === stepIdx ? 'active' : ''}">${i < stepIdx ? '✓' : i + 1}</div>
          <div class="step-label ${i < stepIdx ? 'done' : i === stepIdx ? 'active' : ''}">${s}</div>
        </div>
        ${i < 4 ? `<div class="step-line ${i < stepIdx ? 'done' : ''}" style="margin-top:18px"></div>` : ''}
      </div>`).join('');

    window._currentAppId = id;

    document.getElementById('page-content').innerHTML = `
      <!-- Header with Back Button -->
      <div class="flex items-start gap-3 mb-4">
        <button class="btn btn-outline btn-sm btn-icon" onclick="goBack()" title="Go back" style="margin-top:4px">←</button>
        <div style="flex:1">
          <div class="flex items-center gap-3 flex-wrap">
            <div class="page-title" style="font-size:20px">${app.approval_type_name || 'Application'}</div>
            ${badge(app.status)}
          </div>
          <div class="text-muted mt-1">
            App No: <strong>${app.application_number || '—'}</strong>
            · ${app.business_name || ''}
            · ${app.department_name || ''}
          </div>
        </div>
        <div class="flex gap-2 flex-shrink-0">
          ${canSubmit  ? `<button class="btn btn-primary" id="submit-app-btn"  onclick="submitApplication('${id}')">Submit Application</button>` : ''}
          ${canCorrect ? `<button class="btn btn-amber"   id="correction-btn"  onclick="submitCorrection('${id}')">Submit Correction</button>` : ''}
        </div>
      </div>

      <!-- Status Alerts -->
      ${app.status === 'CORRECTION_REQUIRED' && app.correction_notes
        ? `<div class="warning-box mb-4"><strong>⚠️ Correction Required:</strong> ${app.correction_notes}</div>` : ''}
      ${app.status === 'REJECTED' && app.rejection_reason
        ? `<div class="danger-box mb-4"><strong>✗ Rejected:</strong> ${app.rejection_reason}</div>` : ''}
      ${app.status === 'APPROVED' && app.certificate
        ? `<div class="success-box mb-4 flex justify-between items-start flex-wrap gap-3">
             <div>
               <strong>🏅 Certificate Issued</strong><br>
               <span class="text-sm">${app.certificate.certificate_number}</span><br>
               <span class="text-xs text-muted">Valid until: ${fmtDate(app.certificate.valid_until)}</span><br>
               <span class="text-xs" style="color:var(--amber)">⚠️ PROTOTYPE CERTIFICATE — Not a government-issued document</span>
             </div>
             <button class="btn btn-success btn-sm" onclick="viewCertificate(${JSON.stringify(app.certificate).replace(/"/g,'&quot;')})">
               🏅 View Certificate
             </button>
           </div>` : ''}

      <!-- Journey -->
      <div class="card mb-4">
        <div style="font-size:15px;font-weight:700;margin-bottom:16px">Application Journey</div>
        <div class="flex" style="overflow-x:auto;padding-bottom:8px">${journeyHTML}</div>
      </div>

      <!-- Main Content Grid -->
      <div class="grid-2" style="align-items:start">
        <!-- Documents Panel -->
        <div class="card">
          <div class="flex justify-between items-center mb-4">
            <div style="font-weight:700">Required Documents</div>
            ${canSubmit || canCorrect
              ? `<button class="btn btn-primary btn-sm" onclick="showUploadModal('${id}')">📎 Upload</button>` : ''}
          </div>
          ${reqs.length === 0 && docs.length === 0
            ? '<p class="text-muted text-sm">No document requirements defined.</p>' : ''}
          ${reqs.map(r => `
            <div style="display:flex;align-items:center;gap:10px;padding:12px;background:${r.uploaded ? '#f0fdf4' : '#f8fafc'};border:1px solid ${r.uploaded ? '#86efac' : 'var(--border)'};border-radius:10px;margin-bottom:8px">
              <div style="width:32px;height:32px;border-radius:8px;background:${r.uploaded ? '#dcfce7' : '#f1f5f9'};display:flex;align-items:center;justify-content:center;flex-shrink:0">
                ${r.uploaded ? '✓' : '○'}
              </div>
              <div style="flex:1;min-width:0">
                <div class="text-sm font-bold">${r.requirement.name}</div>
                <div class="text-xs text-muted">${r.requirement.description || ''}</div>
                ${r.document ? `<div class="text-xs mt-1 text-blue">${r.document.filename}</div>` : ''}
              </div>
              <div class="flex items-center gap-2 flex-shrink-0">
                ${r.requirement.is_mandatory && !r.uploaded ? '<span class="text-xs text-red font-bold">Required</span>' : ''}
                ${r.document ? badge(r.document.verification_status) : ''}
                ${(canSubmit || canCorrect) && !r.uploaded
                  ? `<button class="btn btn-outline btn-sm" onclick="showUploadModal('${id}','${r.requirement.id}','${r.requirement.name}')">Upload</button>` : ''}
              </div>
            </div>`).join('')}
          ${docs.filter(d => !d.requirement_id).map(doc => `
            <div style="display:flex;align-items:center;gap:10px;padding:12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;margin-bottom:8px">
              <div style="font-size:20px">📎</div>
              <div>
                <div class="text-sm font-bold">${doc.filename}</div>
                <div class="text-xs text-muted">${doc.doc_type} · ${((doc.file_size || 0) / 1024).toFixed(1)} KB</div>
              </div>
            </div>`).join('')}
        </div>

        <!-- Info + Timeline Panel -->
        <div class="flex flex-col gap-4">
          <div class="card">
            <div style="font-weight:700;margin-bottom:14px">Application Details</div>
            ${[
              ['Application No.', app.application_number || '—'],
              ['Department',      app.department_name    || '—'],
              ['Submitted',       app.submission_date    ? fmtDate(app.submission_date) : 'Not submitted'],
              ['SLA Deadline',    fmtDate(app.sla_deadline) || '—'],
              ['Assigned Officer',app.assigned_officer_name || 'Not assigned'],
            ].map(([k,v]) => `
              <div class="flex justify-between" style="padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px">
                <span class="text-muted">${k}</span>
                <span style="font-weight:600;text-align:right;max-width:60%">${v}</span>
              </div>`).join('')}
          </div>

          <div class="card">
            <div style="font-weight:700;margin-bottom:14px">Status Timeline</div>
            ${(app.status_history || []).slice().reverse().map((sh, i, arr) => `
              <div class="flex gap-3 mb-3">
                <div class="flex flex-col items-center">
                  <div style="width:10px;height:10px;border-radius:50%;background:${i === 0 ? 'var(--blue)' : '#e2e8f0'};flex-shrink:0;margin-top:4px"></div>
                  ${i < arr.length - 1 ? '<div style="width:1px;flex:1;background:#e2e8f0;margin:4px 0 0"></div>' : ''}
                </div>
                <div style="padding-bottom:8px">
                  ${badge(sh.status)}
                  <div class="text-xs text-muted mt-1">${sh.changed_by_name || 'System'} · ${fmtDateTime(sh.created_at)}</div>
                  ${sh.notes ? `<div class="text-xs text-muted" style="font-style:italic">"${sh.notes}"</div>` : ''}
                </div>
              </div>`).join('')}
          </div>
        </div>
      </div>`;
  } catch (e) {
    showError(e.message);
  }
};

// ── Submit Application ──
window.submitApplication = async function (id) {
  const btn = document.getElementById('submit-app-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Submitting...'; }
  try {
    await api('POST', `/applications/${id}/submit`, { force_submit: true });
    toast('Application submitted successfully!', 'success');
    navigate('application-detail', { applicationId: id });
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Submit Application'; }
  }
};

// ── Submit Correction ──
window.submitCorrection = async function (id) {
  const btn = document.getElementById('correction-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Submitting...'; }
  try {
    await api('POST', `/applications/${id}/correction`, { notes: 'Correction submitted by applicant' });
    toast('Correction submitted!', 'success');
    navigate('application-detail', { applicationId: id });
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Submit Correction'; }
  }
};

// ── Upload Document Modal ──
window.showUploadModal = function (appId, reqId, reqName) {
  const docTypes = ['PAN','IDENTITY','BUSINESS_REGISTRATION','FIRE_SAFETY','LAYOUT_PLAN','PROPERTY_DOCS','FSSAI','POLLUTION_CONSENT','FACTORY_LICENCE','LABOUR_REG','OTHER'];
  document.getElementById('modal-title').textContent = 'Upload ' + (reqName || 'Document');
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label>Document Type</label>
      <select id="doc-type-sel">
        ${docTypes.map(t => `<option value="${t}">${t.replace(/_/g,' ')}</option>`).join('')}
      </select>
    </div>
    <div class="upload-area" id="upload-area" onclick="document.getElementById('file-inp').click()">
      <input type="file" id="file-inp" style="display:none" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" onchange="onFileSelect(this)">
      <div style="font-size:32px;margin-bottom:8px">📎</div>
      <div style="font-weight:600;margin-bottom:4px">Click to select file</div>
      <div class="text-xs text-muted">PDF, PNG, JPG, DOC — Max 16 MB</div>
      <div id="file-name" style="margin-top:10px;font-weight:600;color:var(--blue)"></div>
    </div>
    <div class="warning-box mt-3">📝 Demo: OCR extraction is simulated. Files are stored on the local server.</div>
    <div id="ocr-result" class="mt-3"></div>
    <div class="flex gap-3 mt-4">
      <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" style="flex:1" id="upload-btn" onclick="doUpload('${appId}','${reqId || ''}')">
        📤 Upload & Extract
      </button>
    </div>`;
  openModal();
};

window.onFileSelect = function (inp) {
  if (inp.files[0]) {
    document.getElementById('file-name').textContent = `✅ ${inp.files[0].name} (${(inp.files[0].size / 1024).toFixed(1)} KB)`;
    document.getElementById('upload-area').classList.add('has-file');
  }
};

window.doUpload = async function (appId, reqId) {
  const fileInp = document.getElementById('file-inp');
  if (!fileInp.files[0]) { toast('Please select a file first', 'warning'); return; }
  const btn = document.getElementById('upload-btn');
  btn.disabled = true; btn.textContent = '⏳ Uploading...';
  try {
    const fd = new FormData();
    fd.append('file', fileInp.files[0]);
    fd.append('application_id', appId);
    fd.append('doc_type', document.getElementById('doc-type-sel').value);
    if (reqId) fd.append('requirement_id', reqId);
    const d = await apiUpload('/documents/upload', fd);
    toast('Document uploaded!', 'success');
    if (d.ocr_result) {
      const ocr = d.ocr_result;
      document.getElementById('ocr-result').innerHTML = `
        <div class="info-box">
          <div style="font-weight:700;margin-bottom:6px">
            OCR Extraction Result
            ${ocr.is_mock ? '<span class="badge badge-amber" style="font-size:10px">MOCK (DEMO)</span>' : ''}
          </div>
          ${ocr.note ? `<div class="text-sm mb-2">${ocr.note}</div>` : ''}
          ${Object.entries(ocr.extracted_fields || {}).map(([k, v]) =>
            `<div class="text-sm"><strong style="text-transform:capitalize">${k.replace(/_/g,' ')}:</strong> ${v}</div>`).join('')}
        </div>`;
    }
    setTimeout(() => { closeModal(); navigate('application-detail', { applicationId: appId }); }, 2000);
  } catch (e) {
    toast(e.message, 'error');
    btn.disabled = false;
    btn.textContent = '📤 Upload & Extract';
  }
};
