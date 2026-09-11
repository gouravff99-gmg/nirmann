// =============================================
//  NIRMAN — Register Business Wizard
//  File: frontend/js/pages/create-business.js
//
//  Uses window.wizard* globals so onclick
//  handlers inside innerHTML strings can reach them.
// =============================================

PAGES['create-business'] = function () {
  // Reset wizard state
  window.wizardStep = 1;
  window.wizardFormData = {
    name: '', owner_name: '', business_type: '', sector: '',
    state: '', district: '', city: '', address: '',
    investment_amount: '', employee_count: '',
    is_manufacturing: false, handles_food: false, involves_construction: false,
    uses_hazardous: false, uses_heavy_machinery: false, has_physical_infra: true,
    env_approval_applicable: false,
  };

  // Expose methods globally for onclick handlers
  window.wizardRender  = _wizardRender;
  window.wizardNext    = _wizardNext;
  window.wizardBack    = _wizardBack;
  window.wizardSubmit  = _wizardSubmit;
  window.wizardToggle  = function (key) {
    window.wizardFormData[key] = !window.wizardFormData[key];
    _wizardRender();
  };

  _wizardRender();
};

/* ─────── RENDER ─────── */
function _wizardRender () {
  const step      = window.wizardStep;
  const fd        = window.wizardFormData;
  const stepNames = ['Business Info','Location','Size & Scale','Operations','Review & Submit'];
  const total     = stepNames.length;

  // Step indicator HTML
  let stepsHTML = '';
  for (let i = 0; i < total; i++) {
    const done   = step > i + 1;
    const active = step === i + 1;
    stepsHTML += `
      <div class="step-col">
        <div class="step-circle ${done ? 'done' : active ? 'active' : ''}">${done ? '✓' : i + 1}</div>
        <div class="step-label ${done ? 'done' : active ? 'active' : ''}">${stepNames[i]}</div>
      </div>
      ${i < total - 1 ? `<div class="step-line ${step > i + 1 ? 'done' : ''}"></div>` : ''}`;
  }

  // Form body per step
  const bTypes  = ['FOOD_PROCESSING_UNIT','MANUFACTURING_UNIT','RESTAURANT','RETAIL_BUSINESS','CONSTRUCTION_PROJECT','SERVICE_BUSINESS','WHOLESALE_TRADE','OTHER'];
  const sectors = ['FOOD_PROCESSING','FOOD_SERVICE','RESTAURANT','MANUFACTURING','ELECTRONICS','CONSTRUCTION','REAL_ESTATE','RETAIL','WHOLESALE','SERVICE','HEALTHCARE','EDUCATION','OTHER'];
  const states  = ['Andhra Pradesh','Assam','Bihar','Chhattisgarh','Delhi','Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka','Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal'];

  let bodyHTML = '';

  if (step === 1) {
    bodyHTML = `
      <div class="form-group">
        <label>Business Name <span style="color:var(--red)">*</span></label>
        <input id="f-name" value="${fd.name}" placeholder="e.g. FreshBite Foods Pvt Ltd" oninput="window.wizardFormData.name=this.value">
        <div class="field-error" id="err-name">⚠ Please enter your business name.</div>
      </div>
      <div class="form-group">
        <label>Owner / Proprietor Name <span style="color:var(--red)">*</span></label>
        <input id="f-owner" value="${fd.owner_name}" placeholder="Full legal name" oninput="window.wizardFormData.owner_name=this.value">
        <div class="field-error" id="err-owner">⚠ Please enter the owner's full name.</div>
      </div>
      <div class="grid-2">
        <div class="form-group">
          <label>Business Type <span style="color:var(--red)">*</span></label>
          <select id="f-btype" onchange="window.wizardFormData.business_type=this.value">
            <option value="">Select type...</option>
            ${bTypes.map(t => `<option value="${t}" ${fd.business_type === t ? 'selected' : ''}>${t.replace(/_/g,' ')}</option>`).join('')}
          </select>
          <div class="field-error" id="err-btype">⚠ Please select a business type.</div>
        </div>
        <div class="form-group">
          <label>Sector / Industry <span style="color:var(--red)">*</span></label>
          <select id="f-sector" onchange="window.wizardFormData.sector=this.value">
            <option value="">Select sector...</option>
            ${sectors.map(s => `<option value="${s}" ${fd.sector === s ? 'selected' : ''}>${s.replace(/_/g,' ')}</option>`).join('')}
          </select>
          <div class="field-error" id="err-sector">⚠ Please select a sector.</div>
        </div>
      </div>`;

  } else if (step === 2) {
    bodyHTML = `
      <div class="grid-2">
        <div class="form-group">
          <label>State <span style="color:var(--red)">*</span></label>
          <select id="f-state" onchange="window.wizardFormData.state=this.value">
            <option value="">Select state...</option>
            ${states.map(s => `<option value="${s}" ${fd.state === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
          <div class="field-error" id="err-state">⚠ Please select your state.</div>
        </div>
        <div class="form-group">
          <label>District</label>
          <input value="${fd.district}" placeholder="e.g. Bengaluru Urban" oninput="window.wizardFormData.district=this.value">
        </div>
      </div>
      <div class="form-group">
        <label>City / Town</label>
        <input value="${fd.city}" placeholder="e.g. Bengaluru" oninput="window.wizardFormData.city=this.value">
      </div>
      <div class="form-group">
        <label>Business Address</label>
        <textarea placeholder="Full address with PIN code" oninput="window.wizardFormData.address=this.value">${fd.address}</textarea>
      </div>`;

  } else if (step === 3) {
    const invest = parseFloat(fd.investment_amount);
    const msme   = invest > 10000000 ? '🏭 Large Enterprise' : invest > 2500000 ? '🏢 Medium Enterprise' : '🏪 Small / Micro Enterprise';
    bodyHTML = `
      <div class="grid-2">
        <div class="form-group">
          <label>Total Investment (₹)</label>
          <input type="number" value="${fd.investment_amount}" placeholder="e.g. 5000000"
            oninput="window.wizardFormData.investment_amount=this.value;_wizardRender()">
          <div class="text-xs text-muted mt-1">Used for MSME classification</div>
        </div>
        <div class="form-group">
          <label>Number of Employees</label>
          <input type="number" value="${fd.employee_count}" placeholder="e.g. 25"
            oninput="window.wizardFormData.employee_count=this.value">
          <div class="text-xs text-muted mt-1">Affects labour law requirements</div>
        </div>
      </div>
      ${fd.investment_amount
        ? `<div class="info-box mt-2"><strong>MSME Classification (Indicative):</strong> ${msme} <span class="text-xs text-muted">— Verify with official MSME guidelines</span></div>`
        : ''}`;

  } else if (step === 4) {
    const ops = [
      ['is_manufacturing',       'Will you manufacture or process products?',          'Factory Licence may be required'],
      ['handles_food',           'Will you handle, process or serve food?',            'FSSAI Licence and Health NOC required'],
      ['involves_construction',  'Will construction or renovation be involved?',        'Building plan approval required'],
      ['uses_hazardous',         'Will you use or store hazardous materials?',          'Hazardous material licence required'],
      ['uses_heavy_machinery',   'Will you use heavy or industrial machinery?',         'Electrical safety certificate required'],
      ['has_physical_infra',     'Does your business have physical premises?',          'Fire NOC and local permits required'],
      ['env_approval_applicable','May your operations have environmental impact?',      'Pollution control consent required'],
    ];
    bodyHTML = `
      <div class="warning-box mb-4">Select all that apply — your answers determine which approvals are required.</div>
      ${ops.map(([key, label, hint]) => `
        <div style="display:flex;align-items:flex-start;gap:12px;padding:14px;
            border:1.5px solid ${fd[key] ? 'var(--blue)' : 'var(--border)'};
            border-radius:10px;cursor:pointer;
            background:${fd[key] ? 'var(--blue-light)' : 'white'};
            margin-bottom:10px;transition:all 0.15s"
            onclick="window.wizardToggle('${key}')">
          <div style="width:20px;height:20px;border-radius:4px;
              border:2px solid ${fd[key] ? 'var(--blue)' : '#cbd5e1'};
              background:${fd[key] ? 'var(--blue)' : 'white'};
              display:flex;align-items:center;justify-content:center;
              flex-shrink:0;margin-top:2px;transition:all 0.15s">
            ${fd[key] ? '<span style="color:white;font-size:12px;font-weight:900">✓</span>' : ''}
          </div>
          <div>
            <div style="font-size:14px;font-weight:600">${label}</div>
            <div class="text-xs text-muted mt-1">${hint}</div>
          </div>
        </div>`).join('')}`;

  } else if (step === 5) {
    // Review screen
    const selectedOps = [
      fd.is_manufacturing        && 'Manufacturing',
      fd.handles_food            && 'Food Handling',
      fd.involves_construction   && 'Construction',
      fd.uses_hazardous          && 'Hazardous Materials',
      fd.uses_heavy_machinery    && 'Heavy Machinery',
      fd.has_physical_infra      && 'Physical Premises',
      fd.env_approval_applicable && 'Environmental Impact',
    ].filter(Boolean);
    const invest = parseFloat(fd.investment_amount);
    const msme   = invest > 10000000 ? 'Large Enterprise' : invest > 2500000 ? 'Medium Enterprise' : 'Small / Micro Enterprise';

    bodyHTML = `
      <div class="info-box mb-4"><strong>📋 Review your details before submitting.</strong> Use ← Back to make changes.</div>
      <div class="grid-2" style="gap:12px">
        <div style="border:1px solid var(--border);border-radius:10px;padding:16px">
          <div style="font-weight:700;color:var(--blue);margin-bottom:12px">Business Information</div>
          <div class="cert-field"><span class="cert-field-label">Business Name</span><span class="cert-field-value">${fd.name || '—'}</span></div>
          <div class="cert-field"><span class="cert-field-label">Owner Name</span><span class="cert-field-value">${fd.owner_name || '—'}</span></div>
          <div class="cert-field"><span class="cert-field-label">Business Type</span><span class="cert-field-value">${(fd.business_type || '—').replace(/_/g,' ')}</span></div>
          <div class="cert-field"><span class="cert-field-label">Sector</span><span class="cert-field-value">${(fd.sector || '—').replace(/_/g,' ')}</span></div>
        </div>
        <div style="border:1px solid var(--border);border-radius:10px;padding:16px">
          <div style="font-weight:700;color:var(--blue);margin-bottom:12px">Location</div>
          <div class="cert-field"><span class="cert-field-label">State</span><span class="cert-field-value">${fd.state || '—'}</span></div>
          <div class="cert-field"><span class="cert-field-label">City</span><span class="cert-field-value">${fd.city || '—'}</span></div>
          <div class="cert-field"><span class="cert-field-label">District</span><span class="cert-field-value">${fd.district || '—'}</span></div>
        </div>
        <div style="border:1px solid var(--border);border-radius:10px;padding:16px">
          <div style="font-weight:700;color:var(--blue);margin-bottom:12px">Scale & Operations</div>
          <div class="cert-field"><span class="cert-field-label">Investment</span><span class="cert-field-value">₹${fd.investment_amount ? parseInt(fd.investment_amount).toLocaleString('en-IN') : '—'}</span></div>
          <div class="cert-field"><span class="cert-field-label">Employees</span><span class="cert-field-value">${fd.employee_count || '—'}</span></div>
          <div class="cert-field"><span class="cert-field-label">MSME Category</span><span class="cert-field-value">${msme}</span></div>
        </div>
        <div style="border:1px solid var(--border);border-radius:10px;padding:16px">
          <div style="font-weight:700;color:var(--blue);margin-bottom:12px">Selected Operations</div>
          ${selectedOps.length === 0
            ? '<div class="text-muted text-sm">None selected</div>'
            : selectedOps.map(op => `<div class="badge badge-blue" style="margin-bottom:6px">${op}</div> `).join('')}
        </div>
      </div>
      <div class="warning-box mt-4">⚠️ This will register your business and generate a customised approval checklist.</div>`;
  }

  // Navigation buttons
  const backLabel  = step === 1 ? 'Cancel' : '← Back';
  const backAction = step === 1 ? "navigate('businesses')" : 'window.wizardBack()';
  const nextBtn    = step < total
    ? `<button class="btn btn-primary" onclick="window.wizardNext()">Next →</button>`
    : `<button class="btn btn-success" id="wizard-submit-btn" onclick="window.wizardSubmit()">🎯 Register Business</button>`;

  document.getElementById('page-content').innerHTML = `
    <div class="flex items-center gap-3 mb-4">
      <button class="btn btn-outline btn-sm" onclick="${backAction}">←</button>
      <div>
        <div class="page-title">Register Business</div>
        <div class="page-subtitle">Step ${step} of ${total} — ${stepNames[step - 1]}</div>
      </div>
    </div>

    <div class="step-flow mb-4" style="max-width:700px">${stepsHTML}</div>

    <div class="card" style="max-width:700px;margin-bottom:16px" id="wizard-card">
      ${bodyHTML}
    </div>

    <div class="flex justify-between" style="max-width:700px">
      <button class="btn btn-outline" onclick="${backAction}">${backLabel}</button>
      ${nextBtn}
    </div>
  `;
}

/* ─────── NEXT (WITH VALIDATION) ─────── */
function _wizardNext () {
  const step = window.wizardStep;
  const fd   = window.wizardFormData;

  // Helper: mark field error
  const markErr  = (errId, inpId) => {
    document.getElementById(errId)?.classList.add('visible');
    document.getElementById(inpId)?.classList.add('error');
    return false;
  };
  const clearErr = (errId, inpId) => {
    document.getElementById(errId)?.classList.remove('visible');
    document.getElementById(inpId)?.classList.remove('error');
    return true;
  };

  if (step === 1) {
    // Read latest input values before validating
    fd.name          = document.getElementById('f-name')?.value.trim()  || fd.name;
    fd.owner_name    = document.getElementById('f-owner')?.value.trim() || fd.owner_name;
    fd.business_type = document.getElementById('f-btype')?.value        || fd.business_type;
    fd.sector        = document.getElementById('f-sector')?.value       || fd.sector;

    let ok = true;
    ok = (fd.name          ? clearErr('err-name','f-name')   : markErr('err-name','f-name'))   && ok;
    ok = (fd.owner_name    ? clearErr('err-owner','f-owner') : markErr('err-owner','f-owner')) && ok;
    ok = (fd.business_type ? clearErr('err-btype','f-btype') : markErr('err-btype','f-btype')) && ok;
    ok = (fd.sector        ? clearErr('err-sector','f-sector'): markErr('err-sector','f-sector')) && ok;

    if (!ok) { toast('Please fill in all required fields', 'warning'); return; }
  }

  if (step === 2) {
    fd.state = document.getElementById('f-state')?.value || fd.state;
    if (!fd.state) {
      document.getElementById('err-state')?.classList.add('visible');
      document.getElementById('f-state')?.classList.add('error');
      toast('Please select your state', 'warning');
      return;
    }
  }

  if (step === 3) {
    const numInps = document.querySelectorAll('#wizard-card input[type="number"]');
    if (numInps[0]) fd.investment_amount = numInps[0].value;
    if (numInps[1]) fd.employee_count    = numInps[1].value;
  }

  window.wizardStep++;
  _wizardRender();
}

/* ─────── BACK ─────── */
function _wizardBack () {
  if (window.wizardStep > 1) {
    window.wizardStep--;
    _wizardRender();
  }
}

/* ─────── SUBMIT ─────── */
async function _wizardSubmit () {
  const btn = document.getElementById('wizard-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Registering...'; }
  const fd = window.wizardFormData;
  try {
    const payload = {
      ...fd,
      investment_amount: parseFloat(fd.investment_amount) || 0,
      employee_count:    parseInt(fd.employee_count)     || 0,
    };
    const d   = await api('POST', '/businesses/', payload);
    const biz = d.business;
    const cl  = d.checklist || [];
    const docsToApply = cl.reduce((sum, it) => sum + ((it.approval_type && it.approval_type.document_requirements) || []).length, 0);
    toast(`"${biz.name}" registered successfully!`, 'success');

    document.getElementById('page-content').innerHTML = `
      <div style="text-align:center;padding:40px 0 24px">
        <div style="width:72px;height:72px;background:#dcfce7;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:36px;margin:0 auto 16px">✅</div>
        <div class="page-title">Business Registered!</div>
        <div class="page-subtitle">Your customised approval checklist has been generated</div>
      </div>
      <div class="card" style="max-width:700px;margin:0 auto 20px">
        <div class="flex items-center gap-3 mb-4">
          <div style="font-size:28px">${sectorIcon(biz.sector)}</div>
          <div>
            <div style="font-size:17px;font-weight:700">${biz.name}</div>
            <div class="text-muted">${cl.length} approvals · ${docsToApply} documents to apply</div>
          </div>
        </div>
        <div style="max-height:400px;overflow-y:auto">
          ${cl.map((item, i) => {
            const at = item.approval_type || {};
            return `<div class="checklist-item">
              <div class="checklist-num">${i + 1}</div>
              <div style="flex:1">
                <div style="font-weight:700;margin-bottom:4px">${at.name || 'Approval'}</div>
                <div class="text-xs text-muted">${at.department?.name || ''} · Est. ${at.estimated_days || '?'} days</div>
                ${item.why_triggered ? `<div class="text-xs mt-1 text-blue">${item.why_triggered}</div>` : ''}
              </div>
            </div>`;
          }).join('')}
        </div>
        <div class="warning-box mt-4">⚠️ Demonstration checklist. Verify actual requirements with concerned departments.</div>
      </div>
      <div class="flex gap-3 justify-center">
        <button class="btn btn-outline" onclick="navigate('businesses')">My Businesses</button>
        <button class="btn btn-primary" onclick="navigate('business-detail',{businessId:'${biz.id}'})">View Business Dashboard →</button>
      </div>
    `;
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '🎯 Register Business'; }
  }
}
