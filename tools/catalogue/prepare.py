#!/usr/bin/env python3
"""Offline catalogue preparation. Never writes the live snapshot or calls a service."""
import argparse
import csv
import hashlib
import html
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = {'laptop': ('laptops', 'Laptops'), 'desktop': ('desktops', 'Desktops'),
              'accessory': ('accessories', 'Accessories'), 'storage': ('accessories', 'Accessories'),
              'networking': ('networking', 'Networking'), 'monitor': ('monitors', 'Monitors'),
              'ups': ('ups', 'UPS'), 'printer': ('printers', 'Printers')}
REQUIRED = {'source_id', 'title', 'slug', 'sku', 'category', 'condition', 'price_kes',
            'stock_quantity', 'stock_status', 'image_url', 'warranty'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value or ''))).strip()


def clean_copy(value):
    # User confirmed CSV price is the final payable price; do not add tax.
    value = re.sub(r'The listed price excludes 16% VAT\.?', '', value or '', flags=re.I)
    value = re.sub(r',?\s*excluding 16% VAT', '', value, flags=re.I)
    value = re.sub(r'\bEx[ -]?UK\b|\bRefurb\b', 'Refurbished', value, flags=re.I)
    return value.strip()


def number(value, name, integer=False):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f'Invalid {name}: {value!r}') from exc
    if not result.is_finite() or result < 0 or (integer and result != int(result)):
        raise ValueError(f'Invalid {name}: {value!r}')
    return int(result) if integer else float(result)


def specs(row):
    text = plain(row.get('short_specs', '') + ' ' + row.get('description_html', ''))
    result = {}
    cpu = re.search(r'\b(?:Intel\s+)?Core\s+(?:Ultra\s+[3579]|i[3579]|[3579])(?:[-\s]+\d{3,5}[A-Z]{0,3})?|\b(?:AMD\s+)?Ryzen\s*[3579](?:\s+\d{4}[A-Z]{0,3})?|\bApple\s+M[1-4](?:\s+(?:Pro|Max|Ultra))?', text, re.I)
    if cpu:
        result['cpu'] = cpu.group().strip()
    ram = re.search(r'\b(\d{1,3})\s*GB\s*(?:RAM|(?:LP)?DDR[345X]*)\b', text, re.I)
    if ram:
        result['ram_gb'] = int(ram[1])
    storage = re.search(r'\b(\d+(?:\.\d+)?)\s*(GB|TB)\s+(?:(?:PCIe|Gen\d|NVMe|M\.2)\s+)*(SSD|HDD|eMMC|Storage)\b', text, re.I)
    if storage:
        result['storage_gb'] = float(storage[1]) * (1024 if storage[2].upper() == 'TB' else 1)
        if storage[3].lower() != 'storage':
            result['storage_type'] = storage[3].upper()
    screen = re.search(r'\b(\d{1,2}(?:\.\d+)?)\s*(?:"|inch(?:es)?\b)', text, re.I)
    if screen and 3 <= float(screen[1]) <= 100:
        result['screen_in'] = float(screen[1])
    return result


def normalize(row):
    if not row['title'].strip() or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', row['slug']):
        raise ValueError('Missing title or invalid slug')
    price = number(row['price_kes'], 'price')
    if price <= 0:
        raise ValueError('Price must be positive')
    qty = number(row['stock_quantity'], 'stock quantity', integer=True)
    status = row['stock_status'].lower().replace('_', ' ').strip()
    if status not in ('in stock', 'out of stock') or (status == 'in stock') != (qty > 0):
        raise ValueError('Stock status and quantity disagree')
    condition = {'brand new': 'brand_new', 'ex uk': 'refurbished', 'refurbished': 'refurbished'}.get(row['condition'].lower())
    if not condition:
        raise ValueError('Unsupported condition')
    category, label = CATEGORIES[row['category'].lower()]
    if category == 'laptops' and row.get('source_sheet', '').upper() == 'GAMING':
        category, label = 'gaming_laptops', 'Gaming Laptops'
    warranty_text = row['warranty'].lower()
    match = re.search(r'(\d+)\s*(year|month)', warranty_text)
    if match:
        warranty = int(match[1]) * (12 if match[2] == 'year' else 1)
    elif warranty_text == 'no warranty':
        warranty = 0
    else:
        raise ValueError('Unrecognized warranty')
    compare = number(row.get('compare_at_price') or 0, 'compare-at price')
    return {
        'source_id': row['source_id'], 'slug': row['slug'], 'sku': row['sku'],
        'title': clean_copy(row['title']), 'category': category, 'categories': [label],
        'brand': row.get('brand', ''), 'price_kes': price,
        'compare_at_kes': compare if compare > price else None,
        'short_specs': clean_copy(row.get('short_specs', '')),
        'short_description': clean_copy(row.get('short_description', '')),
        'description': clean_copy(row.get('description_html', '')),
        'seo_title': clean_copy(row.get('meta_title', '')),
        'meta_description': clean_copy(row.get('meta_description', '')),
        'condition': condition, 'warranty_months': warranty, 'stock_qty': qty,
        'in_stock': qty > 0, 'status': 'active', 'featured_home': False,
        'tags': [x.strip() for x in row.get('search_keywords', '').split(',') if x.strip()],
        'collections': [row['source_section']] if row.get('source_section') else [],
        **specs(row),
    }


def prepare_image(source, output_root):
    with Image.open(source) as original:
        original.load()
        image = ImageOps.exif_transpose(original).convert('RGBA')
        size = image.size
        # Contain, never crop or stretch. White also composites transparent originals.
        fitted = ImageOps.contain(image, (960, 960), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (1000, 1000), 'white')
        canvas.paste(fitted, ((1000-fitted.width)//2, (1000-fitted.height)//2), fitted)
        import io
        buffer = io.BytesIO()
        canvas.save(buffer, 'WEBP', quality=88, method=6)
    data = buffer.getvalue()
    sha = digest(data)
    key = f'catalogue-v1/{sha}.webp'
    destination = output_root / 'images' / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or digest(destination.read_bytes()) != sha:
        destination.write_bytes(data)
    return {'key': key, 'sha256': sha, 'bytes': len(data), 'source_dimensions': list(size),
            'dimensions': [1000, 1000], 'upscaled': max(size) < 960}


def prepare_source_image(row, image_root, output, cached=None):
    local = (image_root / row['image_url']).resolve()
    if not local.is_relative_to(image_root) or not local.is_file():
        raise ValueError('Image missing or outside source directory')
    source_hash = digest(local.read_bytes())
    if cached and cached.get('source_sha256') == source_hash and cached.get('transform') == 'contain960-webp88-method6-v1':
        derivative = output / 'images' / cached['key']
        if derivative.is_file() and digest(derivative.read_bytes()) == cached['sha256']:
            return dict(cached)
    return {**prepare_image(local, output), 'source_sha256': source_hash,
            'transform': 'contain960-webp88-method6-v1'}


def tokens(value):
    return set(re.findall(r'[a-z0-9]+', plain(value).lower()))


def suggestions(product, existing):
    results = []
    a = tokens(product['title'])
    for old in existing:
        if product['brand'].lower() != str(old.get('brand', '')).lower():
            continue
        b = tokens(old.get('title', ''))
        score = len(a & b) / max(1, len(a | b))
        shared_models = sorted(t for t in a & b if re.search(r'\d', t) and len(t) >= 3 and not re.fullmatch(r'\d+(gb|tb|th)?', t))
        if score < .35 and not shared_models:
            continue
        conflicts = {k: [product[k], old[k]] for k in ('ram_gb', 'storage_gb', 'condition')
                     if product.get(k) is not None and old.get(k) is not None and product[k] != old[k]}
        results.append({'existing_slug': old['slug'], 'existing_title': old.get('title'),
                        'similarity': round(score, 3), 'shared_model_tokens': shared_models,
                        'configuration_conflicts': conflicts})
    return sorted(results, key=lambda r: -r['similarity'])[:3]


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def prepare(args):
    source = Path(args.input).resolve()
    image_root = Path(args.image_root).resolve()
    output = Path(args.output).resolve()
    if output == ROOT or output.is_relative_to(ROOT / 'src') or output.is_relative_to(image_root):
        raise ValueError('Output must be a separate staging directory')
    decisions = json.loads(Path(args.decisions).read_text())
    if decisions.get('price_policy') != 'csv_final' or decisions.get('inventory_policy') != 'csv_confirmed':
        raise ValueError('Confirmed price and inventory policies required')
    with source.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])):
            raise ValueError('Duplicate CSV column names')
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError(f'Missing columns: {sorted(REQUIRED-set(reader.fieldnames or []))}')
        rows = list(reader)
    if not rows or any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError('Empty or malformed CSV')
    ids = [r['source_id'] for r in rows]
    if len(set(ids)) != len(ids) or '' in ids:
        raise ValueError('Source IDs must be nonempty and unique')
    raw_existing = json.loads(Path(args.existing).read_text())
    existing = raw_existing if isinstance(raw_existing, list) else raw_existing['products']
    old_by_slug = {p['slug']: p for p in existing}
    overrides = decisions.get('rows', {})
    if set(overrides)-set(ids):
        raise ValueError('Decision file contains unknown source IDs')
    output.mkdir(parents=True, exist_ok=True)
    products, images, rejected, matches, excluded = [], [], [], [], []
    seen_targets = set()
    prior_manifest = output / 'image-manifest.json'
    image_cache = {entry['source_id']: entry for entry in json.loads(prior_manifest.read_text())} if prior_manifest.exists() else {}
    pool = ThreadPoolExecutor(max_workers=4)
    image_jobs = {r['source_id']: pool.submit(prepare_source_image, r, image_root, output, image_cache.get(r['source_id']))
                  for r in rows if not overrides.get(r['source_id'], {}).get('exclude')}
    for index, row in enumerate(rows):
        choice = overrides.get(row['source_id'], {})
        if choice.get('exclude'):
            excluded.append({'source_id': row['source_id'], 'reason': choice.get('reason', '')})
            continue
        try:
            product = normalize(row)
            if choice.get('existing_slug'):
                target = choice['existing_slug']
                if target not in old_by_slug or target in seen_targets:
                    raise ValueError('Invalid or multiply assigned existing slug')
                product['slug'] = target
            elif choice.get('slug'):
                product['slug'] = choice['slug']
            if choice.get('sku'):
                product['sku'] = choice['sku']
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', product['slug']):
                raise ValueError('Invalid override slug')
            entry = image_jobs[row['source_id']].result()
            entry.update({'source_id': row['source_id'], 'source_path': row['image_url']})
            images.append(entry)
            product['images'] = [args.public_base.rstrip('/') + '/' + entry['key']]
            products.append(product)
            if choice.get('existing_slug'):
                seen_targets.add(choice['existing_slug'])
            matches.append({'source_id': row['source_id'], 'title': product['title'],
                            'incoming_slug': row['slug'], 'selected_existing_slug': choice.get('existing_slug'),
                            'candidates': suggestions(product, existing)})
        except (ValueError, KeyError, OSError) as exc:
            rejected.append({'source_id': row['source_id'], 'error': str(exc)})
        if (index+1) % 100 == 0:
            print(f'Prepared {index+1}/{len(rows)} source rows', flush=True)
    pool.shutdown(wait=True)
    duplicates = {}
    for field in ('slug', 'sku'):
        grouped = defaultdict(list)
        for product in products:
            grouped[product[field]].append({k: product.get(k) for k in
                ('source_id', 'title', 'slug', 'sku', 'price_kes', 'short_specs', 'warranty_months', 'images')})
        duplicates[field] = {key: value for key, value in grouped.items() if len(value)>1}
    retained = [p for p in existing if p['slug'] not in seen_targets]
    pending_matches = [m['source_id'] for m in matches if m['candidates'] and not m['selected_existing_slug']
                       and not overrides.get(m['source_id'], {}).get('keep_as_new')]
    held_ids = set(pending_matches)
    release_products = [p for p in products if p['source_id'] not in held_ids]
    # An unreviewed incoming collision with an old URL must not replace it silently.
    collisions = sorted({p['slug'] for p in release_products} & {p['slug'] for p in retained})
    summary = {'source_rows': len(rows), 'prepared_rows': len(products), 'rejected_rows': len(rejected),
               'excluded_rows': len(excluded), 'existing_retained': len(retained),
               'existing_updated': len(seen_targets), 'duplicate_slug_groups': len(duplicates['slug']),
               'duplicate_sku_groups': len(duplicates['sku']), 'pending_match_reviews': len(pending_matches),
               'held_for_match_review': len(held_ids), 'release_new_products': len(release_products),
               'release_total_products': len(retained) + len(release_products),
               'image_rows': len(images), 'unique_image_files': len({i['key'] for i in images}),
               'upscaled_image_rows': sum(i['upscaled'] for i in images),
               'ready_to_publish': False, 'production_writes': False}
    report = {'summary': summary, 'input_sha256': digest(source.read_bytes()), 'policies': decisions,
              'duplicates': duplicates, 'rejected': rejected, 'excluded': excluded,
              'existing_url_collisions': collisions, 'pending_match_reviews': pending_matches,
              'release_notes': ['Candidate is for review only; duplicate and identity decisions required.',
                               'Verify photographs depict the correct products before publication.',
                               'Snapshot adapter currently overrides stock quantities; fix before release.',
                               'Review supplied compare-at prices before displaying savings.']}
    write_json(output / 'candidate-new.json', products)
    write_json(output / 'candidate-release.json', release_products)
    write_json(output / 'candidate-merged.json', retained + release_products)
    write_json(output / 'image-manifest.json', images)
    write_json(output / 'match-proposals.json', matches)
    write_json(output / 'review.json', report)
    write_json(output / 'existing-retained.json', retained)
    with (output / 'duplicate-review.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['duplicate_field', 'duplicate_value', 'source_id', 'title', 'price_kes', 'specifications', 'warranty_months'])
        for field, groups in duplicates.items():
            for value, members in groups.items():
                for member in members:
                    writer.writerow([field, value, member['source_id'], member['title'], member['price_kes'], member['short_specs'], member['warranty_months']])
    with (output / 'match-proposals.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['source_id', 'incoming_title', 'existing_slug', 'similarity', 'configuration_conflicts'])
        for match in matches:
            for candidate in match['candidates']:
                writer.writerow([match['source_id'], match['title'], candidate['existing_slug'], candidate['similarity'], json.dumps(candidate['configuration_conflicts'])])
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default=str(ROOT / 'PRODUCT_DATA_DROP/ses_catalogue_generated.csv'))
    parser.add_argument('--image-root', default=str(ROOT / 'PRODUCT_IMAGE_DROP'))
    parser.add_argument('--existing', default=str(ROOT / 'src/data/products_final.json'))
    parser.add_argument('--output', default=str(ROOT / 'output/catalogue-review'))
    parser.add_argument('--decisions', default=str(ROOT / 'tools/catalogue/decisions.json'))
    parser.add_argument('--public-base', required=True, help='Public product-images bucket URL')
    prepare(parser.parse_args())


if __name__ == '__main__':
    main()
