// =============================================
//  NIRMAN — Certificates Page
//  File: frontend/js/pages/certificates.js
// =============================================

PAGES['certificates'] = async function () {
  try {
    const d     = await api('GET', '/certificates/my-certificates');
    const certs = d.certificates || [];

    document.getElementById('page-content').innerHTML = `
      <div class="page-title">Certificates</div>
      <div class="page-subtitle">${certs.length} certificate(s) issued</div>
      <div class="warning-box mb-4">
        ⚠️ All certificates shown here are <strong>DEMO PROTOTYPES</strong> generated for SIH presentation only.
        They are NOT government-issued documents and have no legal validity.
      </div>
      ${certs.length === 0
        ? `<div class="card" style="text-align:center;padding:64px">
             <div style="font-size:52px;margin-bottom:16px">🏅</div>
             <div style="font-size:18px;font-weight:700;margin-bottom:8px">No Certificates Yet</div>
             <p class="text-muted">Certificates appear here when your applications are approved.</p>
           </div>`
        : `<div class="grid-2">
             ${certs.map(cert => {
               const urgency = cert.renewal_urgency;
               const borderColor = urgency === 'URGENT' ? '#fca5a5' : urgency === 'SOON' ? '#fcd34d' : '#86efac';
               const daysColor   = urgency === 'URGENT' ? 'var(--red)' : urgency === 'SOON' ? 'var(--amber)' : 'var(--green)';
               return `
                 <div class="card" style="padding:0;overflow:hidden;border-color:${borderColor}">
                   <!-- Cert Header -->
                   <div style="background:linear-gradient(135deg,#0f2460,#1e40af);color:white;padding:20px 24px">
                     <div style="font-size:10px;color:#fbbf24;font-weight:700;letter-spacing:1px;margin-bottom:6px">
                       ⚠ PROTOTYPE — NOT A GOVERNMENT-ISSUED DOCUMENT
                     </div>
                     <div style="font-size:16px;font-weight:800;margin-bottom:4px">${cert.approval_type_name}</div>
                     <div style="color:#93c5fd;font-size:13px">${cert.business_name || ''}</div>
                   </div>

                   <!-- Cert Details -->
                   <div style="padding:16px 20px">
                     <div class="grid-2" style="gap:10px;font-size:13px;margin-bottom:14px">
                       <div>
                         <div class="text-xs text-muted mb-1">Certificate No.</div>
                         <div style="font-weight:700;font-size:12px;word-break:break-all">${cert.certificate_number}</div>
                       </div>
                       <div>
                         <div class="text-xs text-muted mb-1">Department</div>
                         <div style="font-weight:600">${cert.department_name || '—'}</div>
                       </div>
                       <div>
                         <div class="text-xs text-muted mb-1">Issue Date</div>
                         <div style="font-weight:600">${fmtDate(cert.issue_date)}</div>
                       </div>
                       <div>
                         <div class="text-xs text-muted mb-1">Valid Until</div>
                         <div style="font-weight:700;color:${daysColor}">
                           ${fmtDate(cert.valid_until)}
                           ${cert.days_until_expiry !== undefined ? `<span class="text-xs">(${cert.days_until_expiry}d)</span>` : ''}
                         </div>
                       </div>
                     </div>

                     <!-- Verification ID -->
                     <div style="background:#f8fafc;border-radius:8px;padding:10px;font-size:12px;color:var(--slate);margin-bottom:12px">
                       Verification ID: <span class="font-mono font-bold">${cert.verification_id}</span>
                     </div>

                     <!-- Renewal Warning -->
                     ${urgency === 'URGENT' || urgency === 'SOON'
                       ? `<div style="background:${urgency === 'URGENT' ? '#fef2f2' : '#fffbeb'};border-radius:8px;padding:10px;font-size:13px;font-weight:600;color:${daysColor};margin-bottom:12px">
                            🔔 Renewal due in ${cert.days_until_expiry} day(s)
                          </div>` : ''}

                     <!-- View Button -->
                     <button class="btn btn-primary w-full"
                       onclick="viewCertificate(${JSON.stringify(cert).replace(/"/g,'&quot;')})">
                       🏅 View Certificate
                     </button>
                   </div>
                 </div>`;
             }).join('')}
           </div>`}
    `;
  } catch (e) {
    showError(e.message);
  }
};

/* ─────── CERTIFICATE VIEWER MODAL ─────── */

window.viewCertificate = function (cert) {
  if (typeof cert === 'string') {
    cert = JSON.parse(cert.replace(/&quot;/g, '"'));
  }

  document.getElementById('cert-modal-body').innerHTML = `
    <!-- Certificate Preview -->
    <div class="cert-preview">
      <!-- Blue Header Band -->
      <div class="cert-header-band">
        <div class="flex items-center justify-center gap-3 mb-3">
          <div style="width:40px;height:40px;background:rgba(255,255,255,0.2);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900">N</div>
          <div style="text-align:left">
            <div style="font-size:17px;font-weight:900;letter-spacing:1px">NIRMAN</div>
            <div style="font-size:11px;opacity:0.8">Unified Business Approval Platform</div>
          </div>
        </div>
        <div style="display:inline-block;background:rgba(220,38,38,0.25);border:1px solid rgba(220,38,38,0.5);border-radius:6px;padding:4px 14px;font-size:11px;font-weight:700;letter-spacing:1px;color:#fca5a5">
          ⚠ DEMO — NOT A GOVERNMENT-ISSUED DOCUMENT
        </div>
      </div>

      <!-- Body with Watermark -->
      <div class="cert-body">
        <div class="cert-watermark">DEMO PROTOTYPE</div>

        <!-- Seal -->
        <div style="width:72px;height:72px;border:4px solid #1e40af;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:32px;margin:0 auto 20px;background:#eff6ff">🏅</div>

        <!-- Title -->
        <div style="text-align:center;margin-bottom:24px">
          <div style="font-size:20px;font-weight:900;color:#0f2460;letter-spacing:0.5px">APPROVAL CERTIFICATE</div>
          <div style="font-size:14px;color:var(--slate);margin-top:6px">${cert.approval_type_name || 'Approval'}</div>
        </div>

        <!-- Fields -->
        <div style="padding:0 4px">
          ${[
            ['Certificate Number', cert.certificate_number],
            ['Business Name',      cert.business_name || cert.business?.name || '—'],
            ['Applicant',         cert.applicant_name || nirmanState.user?.name || '—'],
            ['Issuing Department', cert.department_name || '—'],
            ['Issue Date',         fmtDate(cert.issue_date)],
            ['Valid Until',        fmtDate(cert.valid_until)],
            ['Verification ID',    cert.verification_id],
            ['Status',             '<span class="badge badge-green">ACTIVE — DEMO</span>'],
          ].map(([k, v]) => `
            <div class="cert-field">
              <span class="cert-field-label">${k}</span>
              <span class="cert-field-value">${v}</span>
            </div>`).join('')}
        </div>

        <!-- Footer -->
        <div style="margin-top:24px;border-top:2px dashed #e2e8f0;padding-top:20px">
          <div class="flex justify-between items-start flex-wrap gap-3">
            <div style="font-size:11px;color:var(--slate);max-width:280px;line-height:1.7">
              This is a demonstration certificate generated by the NIRMAN SIH 2026 prototype.<br>
              It has <strong>NO legal validity</strong> and is NOT issued by any government authority.<br>
              The verification ID is for demonstration purposes only.
            </div>
            <!-- Mock QR -->
            <div style="text-align:center">
              <div style="width:60px;height:60px;border:2px solid #1e40af;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:700;color:#1e40af;word-break:break-all;padding:4px;line-height:1.3">
                DEMO QR CODE
              </div>
              <div style="font-size:9px;color:var(--slate);margin-top:4px">Non-functional</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-3 mt-4">
      <button class="btn btn-outline" style="flex:1" onclick="closeCertModal()">Close</button>
      <button class="btn btn-primary" style="flex:1"
        onclick="toast('PDF generation is a planned feature. In production this would generate a secure PDF.','info')">
        📥 Download (Demo)
      </button>
    </div>
    <div class="warning-box mt-3" style="font-size:12px">
      ⚠️ SIH 2026 Prototype Certificate — NOT a real government-issued document and has no legal validity.
    </div>
  `;
  openCertModal();
};
