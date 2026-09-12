import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

function readJpegDimensions(buffer: Buffer) {
  assert.equal(buffer.readUInt16BE(0), 0xffd8, 'asset must be a JPEG');

  const startOfFrameMarkers = new Set([
    0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7,
    0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf
  ]);
  let offset = 2;

  while (offset + 8 < buffer.length) {
    if (buffer[offset] !== 0xff) {
      offset += 1;
      continue;
    }

    const marker = buffer[offset + 1];
    if (marker === undefined) break;
    offset += 2;

    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0x00 || marker === 0xff) continue;

    const segmentLength = buffer.readUInt16BE(offset);
    if (startOfFrameMarkers.has(marker)) {
      return {
        height: buffer.readUInt16BE(offset + 3),
        width: buffer.readUInt16BE(offset + 5)
      };
    }

    offset += segmentLength;
  }

  throw new Error('JPEG dimensions were not found');
}

test('default Open Graph asset is social-preview ready', async () => {
  const asset = await readFile(new URL('../public/site-assets/og-default.jpg', import.meta.url));

  assert.deepEqual(readJpegDimensions(asset), { width: 1200, height: 630 });
  assert.ok(asset.byteLength < 300_000, 'default OG asset should remain below 300 KB');
});

test('shared layout emits complete Open Graph and X card metadata', async () => {
  const layout = await readFile(new URL('../src/layouts/Layout.astro', import.meta.url), 'utf8');

  assert.match(layout, /defaultSocialImage = '\/site-assets\/og-default\.jpg'/);
  assert.match(layout, /property="og:site_name" content="SES ICT HUB"/);
  assert.match(layout, /property="og:locale" content="en_KE"/);
  assert.match(layout, /property="og:image:alt" content=\{safeImageAlt\}/);
  assert.match(layout, /property="og:image:width" content="1200"/);
  assert.match(layout, /property="og:image:height" content="630"/);
  assert.match(layout, /name="twitter:card" content="summary_large_image"/);
  assert.match(layout, /name="twitter:image:alt" content=\{safeImageAlt\}/);
});

test('product and article pages set specific Open Graph types', async () => {
  const [productPage, articlePage] = await Promise.all([
    readFile(new URL('../src/pages/product/[slug].astro', import.meta.url), 'utf8'),
    readFile(new URL('../src/pages/blog/[slug].astro', import.meta.url), 'utf8')
  ]);

  assert.match(productPage, /ogType="product"/);
  assert.match(articlePage, /ogType="article"/);
});
