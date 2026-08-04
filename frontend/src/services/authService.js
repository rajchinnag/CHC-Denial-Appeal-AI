/**
 * CHC Pro AI — Auth API Service
 * All Layer 1 API calls. Axios instance with auto-refresh interceptor.
 * Design system: IBM Plex Sans, #003F87 navy, #0073CF teal (design_guidelines.json)
 */
import axios from 'axios';

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// ── Axios instance ─────────────────────────────────────────────────────────
export const api = axios.create({
  baseURL: `${BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
});

// ── Token storage (memory = access, sessionStorage = refresh) ──────────────
let _accessToken = null;

export const tokens = {
  setAccess:  (t) => { _accessToken = t; sessionStorage.setItem('chc_access_token', t); },
  getAccess:  ()  => _accessToken || sessionStorage.getItem('chc_access_token'),
  clearAccess: () => { _accessToken = null; sessionStorage.removeItem('chc_access_token'); },
  setRefresh: (t) => sessionStorage.setItem('chc_refresh', t),
  getRefresh: ()  => sessionStorage.getItem('chc_refresh'),
  clearRefresh: () => sessionStorage.removeItem('chc_refresh'),
  clearAll:   ()  => { _accessToken = null; sessionStorage.removeItem('chc_refresh'); },
};

// ── Request interceptor: attach Bearer token ───────────────────────────────
api.interceptors.request.use((config) => {
  const token = tokens.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor: auto-refresh on 401 ─────────────────────────────
let _refreshing = false;
let _queue = [];

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      if (_refreshing) {
        return new Promise((resolve, reject) => {
          _queue.push({ resolve, reject });
        }).then(() => api(original));
      }
      original._retry = true;
      _refreshing = true;
      const refresh = tokens.getRefresh();
      if (!refresh) {
        tokens.clearAll();
        window.location.href = '/login';
        return Promise.reject(error);
      }
      try {
        const { data } = await axios.post(`${BASE}/api/v1/auth/refresh`,
          { refresh_token: refresh });
        tokens.setAccess(data.access_token);
        _queue.forEach(({ resolve }) => resolve());
        _queue = [];
        return api(original);
      } catch (e) {
        tokens.clearAll();
        _queue.forEach(({ reject }) => reject(e));
        _queue = [];
        window.location.href = '/login';
        return Promise.reject(e);
      } finally {
        _refreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

// ── Helper: extract human-readable error ──────────────────────────────────
export function apiError(err) {
  const d = err?.response?.data;
  if (!d) return 'Network error. Please check your connection.';
  if (typeof d.detail === 'string') return d.detail;
  if (Array.isArray(d.detail)) return d.detail.map(e => e.message).join('. ');
  if (d.errors) return d.errors.map(e => `${e.field}: ${e.message}`).join('. ');
  return 'An unexpected error occurred.';
}

// ═══════════════════════════════════════════════════════════════
// REGISTRATION
// ═══════════════════════════════════════════════════════════════

/** Step 1: Basic info */
export async function registerStep1(data) {
  const r = await api.post('/auth/register/step1', data);
  return r.data; // { session_token, message, expires_in }
}

/** Step 2: NPI + Tax ID */
export async function verifyNPI(session_token, npi, tax_id, entity_type = '1') {
  const r = await api.post('/auth/register/step2/verify-npi', {
    session_token, npi, tax_id, entity_type,
  });
  return r.data; // { npi_verified, oig_clear, pecos_enrolled, npi_detail, message }
}

/** Step 3a: Send OTP */
export async function sendOTP(session_token, channel = 'email') {
  const r = await api.post('/auth/register/step3/send-otp', { session_token, channel });
  return r.data; // { message, expires_in, channel }
}

/** Step 3b: Verify OTP */
export async function verifyOTP(session_token, otp_code) {
  const r = await api.post('/auth/register/step3/verify-otp', { session_token, otp_code });
  return r.data; // { session_token, verified, message }
}

/** Step 4a: Set password */
export async function setPassword(session_token, password, confirm_password) {
  const r = await api.post('/auth/register/step4/set-password', {
    session_token, password, confirm_password,
  });
  return r.data;
}

/** Step 4b: Get TOTP QR code */
export async function setup2FA(session_token) {
  const r = await api.post('/auth/register/step4/setup-2fa', null, {
    params: { session_token },
  });
  return r.data; // { totp_secret, qr_code_url, manual_key, message }
}

/** Step 4b: Confirm first TOTP code */
export async function verify2FA(session_token, totp_code) {
  const r = await api.post('/auth/register/step4/verify-2fa', { session_token, totp_code });
  return r.data;
}

/** Step 5: E-signature + create account */
export async function submitSignature({
  session_token, full_legal_name,
  agreed_to_terms, agreed_to_hipaa_baa, agreed_to_privacy,
  signature_data,
}) {
  const r = await api.post('/auth/register/step5/esignature', {
    session_token, full_legal_name,
    agreed_to_terms, agreed_to_hipaa_baa, agreed_to_privacy,
    signature_data,
  });
  return r.data; // { user_id, registration_complete, message }
}

// ═══════════════════════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════════════════════

/** Login step 1: email + password */
export async function login(email, password) {
  const r = await api.post('/auth/login', { email, password });
  const d = r.data;
  if (!d.requires_2fa) {
    tokens.setAccess(d.access_token);
    if (d.refresh_token) tokens.setRefresh(d.refresh_token);
  }
  return d; // { requires_2fa, mfa_session?, access_token?, user? }
}

/** Login step 2: TOTP MFA */
export async function loginMFA(mfa_session, totp_code) {
  const r = await api.post('/auth/login/mfa', { mfa_session, totp_code });
  const d = r.data;
  tokens.setAccess(d.access_token);
  if (d.refresh_token) tokens.setRefresh(d.refresh_token);
  return d; // { access_token, refresh_token, user }
}

/** Logout */
export async function logout() {
  try {
    await api.post('/auth/logout');
  } finally {
    tokens.clearAll();
  }
}

/** Get current user profile */
export async function getMe() {
  const r = await api.get('/auth/me');
  return r.data;
}

/** Initiate password reset */
export async function resetPassword(email) {
  const r = await api.post('/auth/password/reset', { email });
  return r.data;
}

/** Confirm password reset with code */
export async function confirmReset(email, reset_code, new_password, confirm_password) {
  const r = await api.post('/auth/password/confirm', {
    email, reset_code, new_password, confirm_password,
  });
  return r.data;
}

