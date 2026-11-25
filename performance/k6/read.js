// READ load test: search/listing of villages + village details + population history.
//   k6 run performance/k6/read.js
//   k6 run -e VUS=50 -e DURATION=1m performance/k6/read.js
import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate } from 'k6/metrics';
import { API, login, authHeaders } from './common.js';

const VUS = Number(__ENV.VUS || 20);
const DURATION = __ENV.DURATION || '1m';
const SEED_VILLAGES = Number(__ENV.SEED_VILLAGES || 2000);

export const options = {
  stages: [
    { duration: '10s', target: VUS },   // ramp up
    { duration: DURATION, target: VUS }, // steady load
    { duration: '5s', target: 0 },      // ramp down
  ],
  // Pass/fail targets. Adjust after the first "before" run if needed.
  thresholds: {
    http_req_failed: ['rate<0.01'],      // < 1% errors
    http_req_duration: ['p(95)<500'],    // 95% of requests under 500 ms
    // One threshold per endpoint: k6 then prints a per-endpoint breakdown in the summary.
    'http_req_duration{name:search}': ['p(95)<500'],
    'http_req_duration{name:list_by_governorate}': ['p(95)<500'],
    'http_req_duration{name:village_detail}': ['p(95)<500'],
    'http_req_duration{name:population_history}': ['p(95)<500'],
    checks: ['rate>0.99'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'max'],
};

const errorRate = new Rate('app_errors');
const TERMS = ['Seed Village 1', 'Seed Village 12', 'قرية تجريبية 5', 'Seed', 'قرية'];

export function setup() {
  return { token: login() };
}

function randomId() {
  return 1 + Math.floor(Math.random() * SEED_VILLAGES);
}

export default function (data) {
  const params = authHeaders(data.token);

  group('search villages', () => {
    const q = TERMS[Math.floor(Math.random() * TERMS.length)];
    const gov = 1 + Math.floor(Math.random() * 11);
    const page = 1 + Math.floor(Math.random() * 5);

    const r1 = http.get(`${API}/villages?q=${encodeURIComponent(q)}&page=${page}&page_size=20`,
      { ...params, tags: { name: 'search' } });
    const ok1 = check(r1, { 'search 200': (r) => r.status === 200 });
    errorRate.add(!ok1);

    const r2 = http.get(`${API}/villages?governorate_id=${gov}&sort=name_ar&page=${page}&page_size=20`,
      { ...params, tags: { name: 'list_by_governorate' } });
    errorRate.add(!check(r2, { 'list 200': (r) => r.status === 200 }));
  });

  group('village details + population', () => {
    // Seeded village ids are not guaranteed to start at 1, so 200 or 404 are both "handled";
    // we only treat 5xx as an error.
    const id = randomId();
    const r3 = http.get(`${API}/villages/${id}`, { ...params, tags: { name: 'village_detail' } });
    errorRate.add(!check(r3, { 'detail < 500': (r) => r.status < 500 }));

    const r4 = http.get(`${API}/villages/${id}/population`,
      { ...params, tags: { name: 'population_history' } });
    errorRate.add(!check(r4, { 'population < 500': (r) => r.status < 500 }));
  });

  sleep(Math.random() * 0.5 + 0.2); // "think time" between user actions
}