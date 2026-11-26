import { existsSync, readFileSync } from 'node:fs';
import { parseEnv } from 'node:util';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const envFile = `${root}.env.client.local`;
// Parse values as data; never execute credential files as shell scripts.
const localEnv = existsSync(envFile) ? parseEnv(readFileSync(envFile, 'utf8')) : {};
const env = { ...localEnv, ...process.env, CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV: 'false' };
const [command, ...args] = process.argv.slice(2);
if (!['astro', 'wrangler'].includes(command)) throw new Error('Expected astro or wrangler');
const account = '4b4295025db1d29a5f0a52288da307bb';
if (command === 'wrangler') {
  const configFlag = args.indexOf('--config');
  const configPath = configFlag >= 0 ? args[configFlag + 1] : `${root}wrangler.jsonc`;
  if (JSON.parse(readFileSync(configPath, 'utf8')).account_id !== account) throw new Error('Wrangler config must target the client account');
  env.CLOUDFLARE_ACCOUNT_ID ||= account;
  if (env.CLOUDFLARE_ACCOUNT_ID !== account) throw new Error('Client Cloudflare account mismatch');
  if (args[0] !== 'types' && !env.CLOUDFLARE_API_TOKEN) throw new Error('Set CLOUDFLARE_API_TOKEN in .env.client.local or the environment');
  // Explicit env file prevents Wrangler auto-loading the original account's .env.
  args.push('--env-file', '/dev/null');
}
if (env.PUBLIC_SUPABASE_URL && env.PUBLIC_SUPABASE_URL !== 'https://qpopsroxrljpcryawmpb.supabase.co') {
  throw new Error('Client Supabase URL mismatch');
}
const result = spawnSync(`${root}node_modules/.bin/${command}`, args, { cwd: root, env, stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
