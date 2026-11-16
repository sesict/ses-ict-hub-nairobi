#!/usr/bin/env node
// Upload only content-addressed files from the reviewed manifest. Never overwrite.
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, sep } from 'node:path';
import { createHash } from 'node:crypto';

const args = process.argv.slice(2);
if (args.some(x => !['--apply', '--help'].includes(x))) throw new Error('Unknown argument');
if (args.includes('--help')) {
  console.log('node --env-file-if-exists=.env --env-file-if-exists=.env.local tools/catalogue/upload.mjs [--apply]\nDefault: local validation only. --apply: upload missing content-addressed images and verify public bytes.');
  process.exit(0);
}
const apply = args.includes('--apply');
const root = resolve('output/catalogue-review');
const imageRoot = resolve(root, 'images');
const manifest = JSON.parse(readFileSync(resolve(root, 'image-manifest.json'), 'utf8'));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const unique = new Map();
for (const entry of manifest) {
  if (!/^catalogue-v1\/[a-f0-9]{64}\.webp$/.test(entry.key)) throw new Error('Invalid image key');
  const file = resolve(imageRoot, entry.key);
  if (!file.startsWith(imageRoot + sep)) throw new Error('Invalid image path');
  const data = readFileSync(file);
  if (hash(data) !== entry.sha256 || entry.key !== `catalogue-v1/${entry.sha256}.webp` || data.length !== entry.bytes) {
    throw new Error(`Manifest integrity mismatch: ${entry.key}`);
  }
  unique.set(entry.key, { ...entry, file });
}
if (!apply) {
  console.log(JSON.stringify({ mode: 'dry-run', files: unique.size, bytes: [...unique.values()].reduce((sum, e) => sum + e.bytes, 0), writes: false }, null, 2));
  process.exit(0);
}
const url = (process.env.PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || '').replace(/\/$/, '');
const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!url || !key) throw new Error('Supabase URL and service role key are required');
const publicBase = `${url}/storage/v1/object/public/product-images/`;
const candidate = JSON.parse(readFileSync(resolve(root, 'candidate-new.json'), 'utf8'));
if (candidate.some(p => p.images.some(image => !image.startsWith(publicBase)))) {
  throw new Error('Candidate URLs and upload project disagree');
}
const results = [];
const queue = [...unique.values()];
function checkpoint() {
  const summary = { checked: results.length, total: unique.size, uploaded: results.filter(r => r.uploaded).length, failed: results.filter(r => !r.ok).length };
  writeFileSync(resolve(root, 'upload-report.json'), JSON.stringify({ summary, results }, null, 2) + '\n');
}
async function fetchTimed(url, options = {}) {
  return fetch(url, { ...options, signal: AbortSignal.timeout(60000) });
}
async function worker() {
  while (queue.length) {
    const entry = queue.shift();
    try {
      let response = await fetchTimed(publicBase + entry.key);
      let uploaded = false;
      if (!response.ok) {
        // Supabase may use 400 for an absent object. Require the explicit missing code.
        let missing = response.status === 404;
        if (response.status === 400) {
          const body = await response.json();
          missing = body.error === 'not_found' || String(body.statusCode) === '404';
        }
        if (!missing) throw new Error(`Public read failed: ${response.status}`);
        const upload = await fetchTimed(`${url}/storage/v1/object/product-images/${entry.key}`, {
          method: 'POST', headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'image/webp', 'x-upsert': 'false', 'cache-control': 'max-age=31536000' },
          body: readFileSync(entry.file)
        });
        if (!upload.ok) throw new Error(`Upload failed: ${upload.status}`);
        uploaded = true;
        response = await fetchTimed(publicBase + entry.key);
      }
      if (!response.ok || hash(Buffer.from(await response.arrayBuffer())) !== entry.sha256) {
        throw new Error('Public image bytes do not match manifest');
      }
      results.push({ key: entry.key, ok: true, uploaded, public_url: publicBase + entry.key });
    } catch (error) {
      results.push({ key: entry.key, ok: false, error: error.message });
    }
    if (results.length <= 4 || results.length % 25 === 0) {
      checkpoint();
      console.log(`Checked ${results.length}/${unique.size}; failures: ${results.filter(r => !r.ok).length}`);
    }
  }
}
await Promise.all(Array.from({ length: 4 }, worker));
const summary = { checked: results.length, uploaded: results.filter(r => r.uploaded).length, failed: results.filter(r => !r.ok).length };
writeFileSync(resolve(root, 'upload-report.json'), JSON.stringify({ summary, results }, null, 2) + '\n');
console.log(JSON.stringify(summary, null, 2));
if (summary.failed) process.exitCode = 1;
