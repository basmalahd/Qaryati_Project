// WRITE load test: create village, update it (PATCH), add a population record.
//   k6 run performance/k6/write.js
// NOTE: creates real rows. Slugs start with "seed-village-k6-" so they are easy to clean up.
import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate } from 'k6/metrics';
import { API, login, authHeaders } from './common.js';

const VUS = Number(__ENV.VUS || 10);
const DURATION = __ENV.DURATION || '1m';

export const options = {
  stages: [
    { duration: '10s', target: VUS },
    { duration: DURATION, target: VUS },
    { duration: '5s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
    checks: ['rate>0.99'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'max'],
};

const errorRate = new Rate('app_errors');

export function setup() {
  const token = login();
  const params = authHeaders(token);

  // Write tests need a valid governorate and a valid source (provenance is mandatory).
  const gov = http.get(`${API}/governorates`, params).json();
  const src = http.get(`${API}/sources?page_size=1`, params).json('items');
  if (!gov.length || !src.length) {
    throw new Error('Need at least one governorate and one source. Run the seed script first.');
  }
  return { token, governorateId: gov[0].id, sourceId: src[0].id };
}

export default function (data) {
  const params = authHeaders(data.token);
  // Unique slug per VU + iteration + timestamp (slug is UNIQUE in the DB).
  const slug = `seed-village-k6-${__VU}-${__ITER}-${Date.now()}`;

  group('create village', () => {
    const res = http.post(`${API}/villages`, JSON.stringify({
      slug,
      name_ar: `قرية اختبار ${__VU}-${__ITER}`,
      name_en: `K6 Village ${__VU}-${__ITER}`,
      latitude: 32.0, longitude: 35.0,
      governorate_id: data.governorateId,
    }), { ...params, tags: { name: 'create_village' } });

    const ok = check(res, { 'create 201': (r) => r.status === 201 });
    errorRate.add(!ok);
    if (!ok) return;
    const id = res.json('id');

    const upd = http.patch(`${API}/villages/${id}`,
      JSON.stringify({ name_origin: 'updated by k6', elevation_m: 450 }),
      { ...params, tags: { name: 'update_village' } });
    errorRate.add(!check(upd, { 'update 200': (r) => r.status === 200 }));

    const pop = http.post(`${API}/villages/${id}/population`, JSON.stringify({
      population: 1000 + Math.floor(Math.random() * 5000),
      reference_year: 2020,
      source_id: data.sourceId,
    }), { ...params, tags: { name: 'add_population' } });
    errorRate.add(!check(pop, { 'population 201': (r) => r.status === 201 }));
  });

  sleep(Math.random() * 0.5 + 0.2);
}
