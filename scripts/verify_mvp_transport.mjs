/** Real HTTP integration of React's api.ts through the new sandbox's Vite proxy.
 * Node 22.18+ (native TypeScript stripping). This is NOT a visual/browser E2E test.
 * Cookie handling adapts Node fetch to browser semantics; no API responses mocked.
 */
import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';
import { api, refreshCsrf } from '../frontend/src/api.ts';

const base = new URL(process.argv[2]);
assert(['127.0.0.1', 'localhost'].includes(base.hostname) && base.protocol === 'http:');
const nativeFetch = globalThis.fetch;
let cookies = new Map();
globalThis.fetch = async (path, options = {}) => {
  const headers = new Headers(options.headers);
  headers.set('Cookie', [...cookies].map(([k, v]) => `${k}=${v}`).join('; '));
  headers.set('Origin', base.origin);
  const response = await nativeFetch(new URL(path, base), { ...options, headers });
  for (const value of response.headers.getSetCookie()) {
    const pair = value.split(';')[0];
    const equals = pair.indexOf('=');
    cookies.set(pair.slice(0, equals), pair.slice(equals + 1));
  }
  return response;
};
const password = randomBytes(24).toString('hex');
const email = `transport-${randomUUID()}@example.test`;
const html = await nativeFetch(base);
assert.equal(html.status, 200);
assert.match(await html.text(), /src\/main.tsx/);
await api('auth/register/', 'POST', { email, password, organization_name: 'Transport demo', currency: 'COP' });
await api('auth/logout/', 'POST', {});
await api('auth/login/', 'POST', { email, password }); // api.ts refreshes rotated CSRF token.
const missingCsrf = await globalThis.fetch('/api/v1/inventory/adjustments/', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
});
assert.equal(missingCsrf.status, 403);
const category = await api('categories/', 'POST', { name: `Demo ${randomUUID()}` });
const product = await api('products/', 'POST', { name: 'Everyday shirt', category_id: category.id,
  variants: [{ sku: 'TRANSPORT-DEMO', price: '12.50' }] });
const variant = (await api(`products/${product.id}/variants/`)).results[0];
assert.equal((await api('inventory/adjustments/', 'POST', { variant_id: variant.id, delta: 10,
  reason: 'Demo opening stock' })).quantity, 10);
const sale = await api('sales/', 'POST', { items: [{ variant_id: variant.id, quantity: 3 }] });
assert.equal(sale.total, '37.50');
const inventory = await api('inventory/');
assert.equal(inventory.results.find(row => row.variant_id === variant.id).quantity, 7);
assert.equal((await api('inventory/movements/')).count, 2);
assert.equal((await api(`sales/${sale.id}/`)).items[0].unit_price, '12.50');
const tenantA = cookies;
cookies = new Map();
await refreshCsrf(); // A separate browser context starts with its own CSRF cookie/token.
await api('auth/register/', 'POST', { email: `other-${randomUUID()}@example.test`, password,
  organization_name: 'Other transport tenant', currency: 'COP' });
assert.equal((await api('inventory/')).count, 0);
await assert.rejects(api(`sales/${sale.id}/`), error => error.status === 404);
await assert.rejects(api('sales/', 'POST', { items: [{ variant_id: variant.id, quantity: 1 }] }),
  error => error.status === 404);
cookies = tenantA;
console.log(JSON.stringify({ status: 'passed', transport: 'actual frontend/src/api.ts through Vite',
  loginCsrf: true, missingCsrf: 403, openingStock: 10, sold: 3, remaining: 7,
  total: '37.50', movements: 2, foreignSale: 404, foreignVariant: 404,
  visualBrowserTest: 'BLOCKED: Computer Use could not identify Chrome URL safely' }, null, 2));
