import axios from 'axios';

const API_BASE = '/bot-api/api';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Cookie-based auth (Flask sessions) — no token header needed
client.defaults.withCredentials = true;

// Track 401s to prevent duplicate logout dispatches
let last401Time = 0;
const DEBOUNCE_401_MS = 3000;

// Handle auth errors — dispatch event so AuthContext can react
client.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      const now = Date.now();
      // Debounce: don't fire multiple logout events from concurrent 401s
      if (now - last401Time > DEBOUNCE_401_MS) {
        last401Time = now;
        // Clear token on 401
        localStorage.removeItem('admin_token');
        localStorage.removeItem('admin_user');
        // Dispatch custom event for AuthContext to listen
        window.dispatchEvent(new CustomEvent('auth:session-expired', {
          detail: { message: error.response?.data?.message || 'انتهت الجلسة' },
        }));
      }
    } else if (error.response?.status === 403) {
      console.warn('[api] 403 Forbidden:', error.config?.url);
    }
    return Promise.reject(error);
  }
);

// ── Token storage ──
const TOKEN_KEY = 'admin_token';

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

// Attach token to every request if available
client.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers['X-Admin-Token'] = token;
  }
  return config;
});

// ── Auth (matches web_control.py backend) ──
export const auth = {
  /** Step 1: Request OTP → sends 6-digit code to admin Telegram */
  requestOTP: (password) => client.post('/admin/request-otp', { password }),

  /** Step 2: Verify OTP → get session token */
  verifyOTP: (otp) => client.post('/admin/verify-otp', { otp }),

  /** Logout */
  logout: () => client.post('/admin/logout'),

  /** Check if current token is still valid */
  checkSession: () => client.get('/admin/check-session'),
};

// ── Bot Control ──
export const bot = {
  status: () => client.get('/status'),
  start: () => client.post('/start'),
  stop: () => client.post('/stop'),
  restart: () => client.post('/restart'),
  logs: (n = 50, level) => client.get('/logs', { params: { n, level } }),
  deleteLogs: () => client.delete('/logs'),
};

// ── Stats & Analytics ──
export const stats = {
  overview: () => client.get('/stats'),
  analytics: () => client.get('/analytics'),
  charts: () => client.get('/analytics/charts'),
  reports: () => client.get('/analytics/reports'),
  exportCSV: () => client.get('/export/csv', { responseType: 'blob' }),
  onlineUsers: () => client.get('/online-users'),
};

// ── Users ──
export const users = {
  list: (params = {}) => {
    const searchParams = {};
    if (params.search) searchParams.q = params.search;
    if (params.tier && params.tier !== 'all') searchParams.tier = params.tier;
    if (params.status && params.status !== 'all') searchParams.status = params.status;
    if (params.page) searchParams.page = params.page;
    if (params.per_page) searchParams.per_page = params.per_page;
    if (params.sort) searchParams.sort = params.sort;
    if (params.order) searchParams.order = params.order;

    if (Object.keys(searchParams).length > 0) {
      return client.get('/users/search', { params: searchParams });
    }
    return client.get('/users');
  },
  detail: (id) => client.get(`/users/${id}`),
  ban: (id, reason) => client.post(`/users/${id}/ban`, { reason }),
  unban: (id) => client.post(`/users/${id}/unban`),
  delete: (id) => client.delete(`/users/${id}`),
  setPoints: (id, points) => client.post(`/users/${id}/points`, { points }),
  setTier: (id, tier, expiresIn) => client.post('/admin/promote-user', { user_id: id, tier, expires_in: expiresIn }),
  activity: (id) => client.get(`/users/${id}/activity`),
};

// ── Settings ──
export const settings = {
  get: () => client.get('/settings'),
  update: (data) => client.post('/settings', data),
  general: {
    get: () => client.get('/settings/general'),
    update: (data) => client.put('/settings/general', data),
  },
  platforms: {
    get: () => client.get('/settings/platforms'),
    update: (data) => client.post('/settings/platforms', data),
  },
  tierLimits: {
    get: () => client.get('/tier-limits'),
    update: (data) => client.post('/tier-limits', data),
  },
  siteStyle: {
    get: () => client.get('/site-style'),
    update: (data) => client.post('/admin/site-style', data),
  },
};

// ── Admin ──
export const admin = {
  info: () => client.get('/admin/info'),
  changePassword: (password) => client.post('/admin/change-password', { password }),
  broadcast: (message) => client.post('/admin/broadcast', { message }),
  sendMessage: (userId, message) => client.post('/admin/send-message', { user_id: userId, message }),
  restartServer: () => client.post('/admin/restart-server'),
  activityLog: () => client.get('/admin/activity-log'),
  promoteUser:         (userId, tier, expiresIn) => client.post('/admin/promote-user', { user_id: userId, tier, expires_in: expiresIn }),
  revokeTier:          (userId) => client.post('/admin/revoke-tier', { user_id: userId }),
  getUserExpiry:       (userId) => client.get('/admin/get-user-expiry', { params: { user_id: userId } }),
  tierConfig: {
    get:    () => client.get('/admin/tier-config'),
    update: (data) => client.post('/admin/tier-config', data),
  },
  banUser: (userId) => client.post('/admin/bot-user-action', { action: 'ban', user_id: userId }),
  refreshNames: (userIds) => client.post('/admin/refresh-names', { user_ids: userIds || [] }),
  settings: {
    get: () => client.get('/admin/settings'),
    update: (data) => client.post('/admin/settings', data),
  },

  // ── Ghost Mode (وضع الشبح) ──
  /** تغيير مستوى مستخدم بصمت - بدون أي إشعار */
  ghostSetTier: (userId, tier, expiresIn) =>
    client.post('/admin/ghost-set-tier', { user_id: userId, tier, expires_in: expiresIn }),
  /** جلب سجل عمليات الشبح */
  ghostGetHistory: (params = {}) =>
    client.post('/admin/ghost-get-history', params),
};

// ── Database ──
export const database = {
  info: () => client.get('/database'),
  backup: () => client.post('/database'),
  query: (sql) => client.post('/database', { query: sql }),
  delete: () => client.delete('/database'),
};

// ── System ──
export const system = {
  info: () => client.get('/system'),
  restart: () => client.post('/system'),
};

// ── Platform Settings ──
export const platforms = {
  get: () => client.get('/platforms'),
  update: (data) => client.put('/platforms', data),
};

// ── Login History ──
export const security = {
  loginHistory: () => client.get('/login-history'),
  unblockIP: (ip) => client.post('/unblock-ip', { ip }),
};

export default client;
