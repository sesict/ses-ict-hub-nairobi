import assert from 'node:assert/strict';
import test from 'node:test';
import { getRuntimeEnv, hasPublicSupabaseConfig } from '../src/lib/runtime';

test('local preview detects missing Supabase credentials without throwing', () => {
  assert.equal(hasPublicSupabaseConfig({ runtime: { env: {} } } as never), false);
});

test('runtime Supabase credentials enable authenticated middleware', () => {
  assert.equal(
    hasPublicSupabaseConfig({
      runtime: {
        env: {
          PUBLIC_SUPABASE_URL: 'https://example.supabase.co',
          PUBLIC_SUPABASE_ANON_KEY: 'anon-key',
          SUPABASE_SERVICE_ROLE_KEY: undefined
        }
      }
    } as never),
    true
  );
});


test('Astro 6 Worker bindings provide server secrets without reading removed runtime getters', () => {
  const locals = {
    user: null,
    profile: null,
    isStaff: false,
    isAdmin: false,
    cloudflareEnv: {
      PUBLIC_SUPABASE_URL: 'https://client.supabase.co',
      PUBLIC_SUPABASE_ANON_KEY: 'publishable-key',
      SUPABASE_SERVICE_ROLE_KEY: 'server-secret',
      TURNSTILE_SECRET_KEY: 'challenge-secret'
    },
    runtime: {
      get env(): never {
        throw new Error('Astro.locals.runtime.env has been removed');
      }
    }
  };
  for (const source of [locals, { locals }]) {
    const env = getRuntimeEnv(source);
    assert.equal(env.SUPABASE_SERVICE_ROLE_KEY, 'server-secret');
    assert.equal(env.TURNSTILE_SECRET_KEY, 'challenge-secret');
    assert.equal(hasPublicSupabaseConfig(source), true);
  }
});
