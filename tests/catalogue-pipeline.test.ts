import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { rawToCatalogRow } from '../src/lib/products';

test('catalogue adapter preserves confirmed stock and merchandising fields', () => {
  const product = rawToCatalogRow({
    slug: 'sample', title: 'Sample', price_kes: 5600, in_stock: true,
    stock_qty: 5, featured_home: false, featured_rank: 0,
  }, 0);
  assert.equal(product.in_stock, true);
  assert.equal(product.stock_qty, 5);
  assert.equal(product.featured_home, false);
  assert.equal(product.featured_rank, 0);

  const soldOut = rawToCatalogRow({
    slug: 'sold-out', title: 'Sold out', price_kes: 5600, in_stock: false, stock_qty: 0,
  });
  assert.equal(soldOut.in_stock, false);
  assert.equal(soldOut.stock_qty, 0);
});

test('catalogue preparation preserves pricing, detects conflicts, and contains images', () => {
  const result = spawnSync('python3', ['-m', 'unittest', 'discover', '-s', 'tools/catalogue', '-p', 'test_*.py'], {
    encoding: 'utf8', timeout: 30000,
  });
  assert.equal(result.status, 0, `${result.stdout || ''}\n${result.stderr || ''}\n${result.error || ''}`);
});
