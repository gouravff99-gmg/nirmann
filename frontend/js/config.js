// =============================================
//  NIRMAN — Configuration
//  File: frontend/js/config.js
// =============================================

const NIRMAN_CONFIG = {
  API_BASE: 'http://localhost:5001/api',
  APP_NAME: 'NIRMAN',
  VERSION: '1.0.0 — SIH 2026',
  DEMO_PASSWORD: 'Demo@1234',
  OFFICER_PASSWORD: 'Demo@1234',

  DEMO_ACCOUNTS: [
    { email: 'applicant@demo.com', role: 'APPLICANT', name: 'Gourav Gadgane',          icon: '👤' },
    { email: 'inspector@demo.com', role: 'OFFICER',  name: 'Arjun Singh · Licence Officer / Inspector', icon: '🏛️' },
    { email: 'admin@demo.com',     role: 'ADMIN',    name: 'System Admin',             icon: '⚙️' },
  ],

  // Navigation items per role
  NAV: {
    APPLICANT: [
      { page: 'dashboard',    icon: '🏠', label: 'Dashboard'         },
      { page: 'businesses',   icon: '🏢', label: 'My Businesses'     },
      { page: 'applications', icon: '📋', label: 'Applications'      },
      { page: 'certificates', icon: '🏅', label: 'Certificates'      },
      { page: 'notifications',icon: '🔔', label: 'Notifications'     },
      { page: 'schemes',      icon: '🛡️', label: 'Schemes & Incentives'},
      { page: 'grievances',   icon: '📩', label: 'Grievances'        },
    ],
    OFFICER: [
      { page: 'officer-dashboard', icon: '🏛️', label: 'Licence Officer / Inspector' },
      { page: 'officer-inbox',     icon: '📥', label: 'Applications Inbox'          },
      { page: 'inspector-dashboard',icon: '🔍', label: 'Inspection Tasks'           },
      { page: 'notifications',     icon: '🔔', label: 'Notifications'               },
    ],
    ADMIN: [
      { page: 'admin-dashboard',   icon: '📊', label: 'Dashboard'       },
      { page: 'admin-applications',icon: '📋', label: 'All Applications'},
      { page: 'admin-users',       icon: '👥', label: 'Users'           },
      { page: 'audit-logs',        icon: '🛡️', label: 'Audit Trail'     },
      { page: 'notifications',     icon: '🔔', label: 'Notifications'   },
    ],
  },

  // Default home page per role
  DEFAULT_PAGE: {
    APPLICANT: 'dashboard',
    ADMIN:     'admin-dashboard',
    OFFICER:   'officer-dashboard',
  },
};
