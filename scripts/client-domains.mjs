import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { parseEnv } from 'node:util';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const envPath = `${root}.env.client.local`;
const env = { ...(existsSync(envPath) ? parseEnv(readFileSync(envPath, 'utf8')) : {}), ...process.env };
const account = '4b4295025db1d29a5f0a52288da307bb';
const zone = 'f1b6d3e1359d5c5837ce547c0da54ccc';
if (env.CLOUDFLARE_ACCOUNT_ID !== account || !env.CLOUDFLARE_API_TOKEN) throw new Error('Client Cloudflare credentials required');
const [mode] = process.argv.slice(2);
if (!['stage-www', 'attach-www', 'attach-apex'].includes(mode)) throw new Error('Expected stage-www, attach-www, or attach-apex');
async function api(path, method = 'GET', body) {
  const headers = { Authorization: `Bearer ${env.CLOUDFLARE_API_TOKEN}` };
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`https://api.cloudflare.com/client/v4${path}`, {
    method, headers, body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(60000)
  });
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error(`Cloudflare ${response.status}: ${JSON.stringify(data.errors)}`);
  return data.result;
}
const wwwWorker = 'ses-ict-hub-www-redirect';
if (mode === 'stage-www') {
  const form = new FormData();
  form.set('metadata', new Blob([JSON.stringify({ main_module: 'www-redirect.js', compatibility_date: '2026-03-09' })], { type: 'application/json' }));
  form.set('www-redirect.js', new Blob([readFileSync(`${root}workers/www-redirect.js`)], { type: 'application/javascript+module' }), 'www-redirect.js');
  await api(`/accounts/${account}/workers/scripts/${wwwWorker}`, 'PUT', form);
  await api(`/accounts/${account}/workers/scripts/${wwwWorker}/subdomain`, 'POST', { enabled: true });
  console.log('Client www redirect staged on workers.dev; production DNS untouched.');
} else {
  const info = await api(`/zones/${zone}`);
  if (info.account.id !== account || info.status !== 'active') throw new Error('Client zone must be active before attaching domains. Keep current nameservers until the cutover checks are complete.');
  const apex = mode === 'attach-apex';
  const hostname = apex ? 'sesicthub.co.ke' : 'www.sesicthub.co.ke';
  await api(`/accounts/${account}/workers/domains`, 'PUT', { hostname, zone_id: zone, service: apex ? 'ses-hub-superbase-stack-app' : wwwWorker, environment: 'production' });
  if (apex) {
    const configPath = `${root}wrangler.jsonc`;
    const config = JSON.parse(readFileSync(configPath, 'utf8'));
    config.routes = [{ pattern: hostname, custom_domain: true, zone_id: zone }];
    writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n');
  }
  console.log(`Attached ${hostname} in the client account. Verify HTTPS before declaring cutover complete.`);
}
