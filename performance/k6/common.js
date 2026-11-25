// Shared helpers for the k6 scripts.
import http from 'k6/http';
import { check, fail } from 'k6';

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const API = `${BASE_URL}/api/v1`;
const EMAIL = __ENV.K6_EMAIL || 'k6-admin@example.com';
const PASSWORD = __ENV.K6_PASSWORD || 'ChangeMe12345';

export const JSON_HEADERS = { 'Content-Type': 'application/json' };

// Log in once (called from setup(), NOT per request, so we measure the API
// under test and not the password hashing of /auth/login).
export function login() {
  const res = http.post(
    `${API}/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: JSON_HEADERS, tags: { name: 'setup_login' } },
  );
  if (!check(res, { 'login 200': (r) => r.status === 200 })) {
    fail(`Login failed (${res.status}). Create the user first: see performance/k6/README.md`);
  }
  return res.json('access_token');
}

export function authHeaders(token) {
  return { headers: { ...JSON_HEADERS, Authorization: `Bearer ${token}` } };
}
