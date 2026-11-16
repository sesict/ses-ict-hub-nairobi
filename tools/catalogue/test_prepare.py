import importlib.util
import tempfile
import unittest
import csv
import json
from types import SimpleNamespace
from pathlib import Path
from PIL import Image

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).with_name('prepare.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class CataloguePreparationTests(unittest.TestCase):
    def row(self):
        return dict(source_id='ses:test:1', title='HP Test Ex UK', slug='hp-test', sku='HP-TEST',
                    category='laptop', condition='Ex UK', price_kes='10000', stock_quantity='5',
                    stock_status='In Stock', warranty='1 Year Warranty', brand='HP',
                    description_html='<p>KES 10,000, excluding 16% VAT.</p>',
                    short_description='The listed price excludes 16% VAT.',
                    short_specs='Intel Core i5 16GB DDR4 512GB PCIe Gen4 NVMe M.2 SSD',
                    meta_title='Test SEO', meta_description='Test description')

    def test_mapping_preserves_confirmed_price_and_quantity(self):
        row = p.normalize(self.row())
        self.assertEqual((row['price_kes'], row['stock_qty'], row['warranty_months']), (10000, 5, 12))
        self.assertEqual(row['condition'], 'refurbished')
        self.assertEqual(row['title'], 'HP Test Refurbished')
        self.assertEqual(row['seo_title'], 'Test SEO')
        self.assertNotIn('VAT', row['description'] + row['short_description'])
        self.assertEqual((row['ram_gb'], row['storage_gb'], row['storage_type']), (16, 512, 'SSD'))

    def test_gpu_memory_not_mistaken_for_ram(self):
        self.assertNotIn('ram_gb', p.specs({'short_specs': 'RTX 5060 8GB graphics; 512GB SSD'}))

    def test_stock_conflict_and_invalid_price_rejected(self):
        for change in ({'stock_quantity': '0'}, {'stock_quantity': '-1'}, {'price_kes': 'NaN'}, {'price_kes': '0'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.normalize(self.row() | change)

    def test_no_warranty_and_out_of_stock(self):
        row = p.normalize(self.row() | {'warranty': 'No warranty', 'stock_quantity': '0', 'stock_status': 'Out of Stock'})
        self.assertEqual(row['warranty_months'], 0)
        self.assertFalse(row['in_stock'])

    def test_image_contains_whole_product_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'original.png'
            Image.new('RGB', (400, 200), 'red').save(source)
            original = source.read_bytes()
            first = p.prepare_image(source, root)
            second = p.prepare_image(source, root)
            self.assertEqual(first, second)
            self.assertEqual(source.read_bytes(), original)
            with Image.open(root / 'images' / first['key']) as image:
                self.assertEqual(image.size, (1000, 1000))
                self.assertGreater(min(image.getpixel((0, 0))), 245)
                self.assertGreater(image.getpixel((500, 500))[0], 240)
            self.assertTrue(first['upscaled'])

    def test_match_flags_different_configuration(self):
        product = p.normalize(self.row())
        candidates = p.suggestions(product, [product | {'slug': 'old-url', 'ram_gb': 8}])
        self.assertEqual(candidates[0]['existing_slug'], 'old-url')
        self.assertEqual(candidates[0]['configuration_conflicts']['ram_gb'], [16, 8])

    def test_rejected_match_cannot_remove_existing_product(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            images = root / 'sources'
            images.mkdir()
            row = self.row() | {'image_url': 'missing.png'}
            source = root / 'source.csv'
            with source.open('w', newline='', encoding='utf-8-sig') as handle:
                # Deliberately reorder headers to verify named-column parsing.
                writer = csv.DictWriter(handle, fieldnames=list(reversed(list(row))))
                writer.writeheader()
                writer.writerow(row)
            old = [{'slug': 'existing-url', 'title': 'Existing HP', 'brand': 'HP'}]
            (root / 'old.json').write_text(json.dumps(old))
            (root / 'decisions.json').write_text(json.dumps({
                'price_policy': 'csv_final', 'inventory_policy': 'csv_confirmed',
                'rows': {row['source_id']: {'existing_slug': 'existing-url'}}
            }))
            p.prepare(SimpleNamespace(input=source, image_root=images, output=root / 'output',
                                      existing=root / 'old.json', decisions=root / 'decisions.json',
                                      public_base='https://example.test/storage/v1/object/public/product-images'))
            merged = json.loads((root / 'output/candidate-merged.json').read_text())
            report = json.loads((root / 'output/review.json').read_text())
            self.assertEqual(merged, old)
            self.assertEqual(report['summary']['rejected_rows'], 1)
            self.assertFalse(report['summary']['ready_to_publish'])

    def test_duplicate_rows_retained_for_review_without_silent_merge(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            images = root / 'sources'
            images.mkdir()
            Image.new('RGB', (1000, 1000), 'white').save(images / 'photo.png')
            row = self.row() | {'image_url': 'photo.png'}
            source = root / 'source.csv'
            with source.open('w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(reversed(list(row))))
                writer.writeheader()
                writer.writerows([row, row | {'source_id': 'ses:test:2', 'price_kes': '12000'}])
            (root / 'old.json').write_text('[]')
            (root / 'decisions.json').write_text(json.dumps({
                'price_policy': 'csv_final', 'inventory_policy': 'csv_confirmed', 'rows': {}}))
            p.prepare(SimpleNamespace(input=source, image_root=images, output=root / 'output',
                                      existing=root / 'old.json', decisions=root / 'decisions.json',
                                      public_base='https://example.test/storage/v1/object/public/product-images'))
            report = json.loads((root / 'output/review.json').read_text())
            self.assertEqual(report['summary']['prepared_rows'], 2)
            self.assertEqual(report['summary']['duplicate_slug_groups'], 1)
            self.assertEqual(report['summary']['unique_image_files'], 1)


if __name__ == '__main__':
    unittest.main()
