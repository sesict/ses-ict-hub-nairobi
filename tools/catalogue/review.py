#!/usr/bin/env python3
"""Render a local, searchable visual review of the prepared catalogue."""
import html
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2] / 'output/catalogue-review'
products = json.loads((root / 'candidate-new.json').read_text())
manifest = {r['source_id']: r for r in json.loads((root / 'image-manifest.json').read_text())}
report = json.loads((root / 'review.json').read_text())
esc = lambda x: html.escape(str(x), quote=True)
cards = []
for p in products:
    asset = manifest[p['source_id']]
    cards.append(f'''<article><img loading="lazy" src="images/{esc(asset['key'])}" width="250" height="250" alt="{esc(p['title'])}">
<h2>{esc(p['title'])}</h2><p>{esc(p['source_id'])}</p><p><strong>KSh {p['price_kes']:,.0f}</strong> · {p['stock_qty']} available · {p['warranty_months']} months warranty</p>
<p>{esc(p['short_specs'])}</p><p class="small">Slug: {esc(p['slug'])}<br>SKU: {esc(p['sku'])}<br>Original image: {esc(asset['source_path'])}<br>{'Enlarged from a smaller original' if asset['upscaled'] else 'Original resolution sufficient'}</p></article>''')
(root / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SES catalogue review — local preview</title><style>
body{font:15px system-ui;margin:24px;background:#f2f5f9;color:#14213b}h1{font-size:26px}h2{font-size:17px}input{box-sizing:border-box;width:100%;padding:14px;border:1px solid #aac;border-radius:10px;margin:16px 0}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px}article{background:white;padding:16px;border-radius:14px;overflow-wrap:anywhere}img{width:100%;height:auto;aspect-ratio:1;object-fit:contain}.small{font-size:12px;color:#526078}a{color:#0069bd}article[hidden]{display:none}
</style><h1>SES catalogue review</h1><p>This is a local review, not the published storefront. Prices and quantities follow your confirmed CSV rules. Images require model and visual review.</p>
<p><a href="review.json">Audit report</a> · <a href="duplicate-review.csv">Duplicate report</a> · <a href="match-proposals.csv">Existing-product match proposals</a></p>
<pre>''' + esc(json.dumps(report['summary'], indent=2)) + '''</pre><label for="search">Search product, source row, model, or SKU</label><input id="search" type="search"><main>''' + ''.join(cards) + '''</main><script>
const cards=Array.from(document.querySelectorAll('article'));document.querySelector('#search').addEventListener('input',event=>{const terms=event.target.value.toLowerCase().trim().split(/[\\s]+/);for(const card of cards){const text=card.textContent.toLowerCase();card.hidden=!terms.every(term=>text.includes(term));}});
</script></html>''')
print(root / 'index.html')
