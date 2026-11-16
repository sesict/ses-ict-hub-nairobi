# November catalogue publication plan

Review date: 2026-11-15. Scope: inspect the new drop and propose publication; no production writes performed.

## Findings

- The storefront, product detail pages, search and WhatsApp checkout use `src/lib/products.ts`, which imports `src/data/products_final.json`. A Supabase products-table import alone will not publish this catalogue. The current local snapshot contains 245 rows.
- The deployment configuration targets `sesicthub.co.ke` through the existing Cloudflare Worker deployment script. The public homepage responded during review. Its deployed revision and full database contents were not verified.
- `PRODUCT_DATA_DROP/ses_catalogue_generated.csv` contains 937 rows, all with positive prices. There are 929 distinct slugs: eight duplicate groups. There are 906 distinct SKUs: 19 duplicate groups containing 31 excess occurrences.
- All 937 image paths resolve beneath `PRODUCT_IMAGE_DROP`, and Pillow opened and verified them. Only 61 are exactly 1000×1000. This checks file integrity, not whether each photo depicts the correct model.
- No new slug matches a slug in the current snapshot. This does not establish that all products are new: model/configuration matching is necessary.
- The existing CSV importer reconstructs rows by position using an older layout. A local dry run rejected all 937 rows and misread condition, warranty and stock columns. Do not apply this file using that importer unchanged.
- The CSV uses `image_url`, `description_html`, `meta_title`, textual warranty and `Ex UK`. The snapshot adapter needs `images`, `description`, `seo_title`, numeric `warranty_months` and normalized condition.
- The snapshot adapter currently forces positive-price products to `in_stock=true` and `stock_qty=1`. It also selects the first 24 rows for homepage featuring. These behaviors need explicit attention during catalogue preparation.
- Every incoming row declares five units, in stock, and VAT-exclusive prices. Checkout sums listed prices without adding VAT. Confirm intended customer prices and real availability before publishing; do not change order calculations as part of this catalogue task.

## Recommended implementation

1. Build a repeatable, header-based converter for this CSV. Produce a candidate snapshot and machine-readable audit without replacing the current snapshot. Preserve source IDs for traceability. Map fields, normalize categories/conditions/warranties, and extract CPU, RAM and storage conservatively.
2. Resolve duplicate slugs and SKUs by checking model, configuration and source rows. Match existing products by identity, retaining existing URLs where appropriate. Report additions, updates, unresolved matches and retirements. Default to retaining unmatched existing products until replacement scope is decided.
3. Resolve price/VAT, stock and discount-reference accuracy. Correct the catalogue adapter to respect supplied stock fields if approved within the implementation scope; leave checkout logic unchanged. Select homepage products deliberately.
4. Prepare separate optimized 1000×1000 image derivatives, preserving originals and product proportions. Review model/image matches, especially duplicate groups and low-resolution originals. Produce an exact upload manifest.
5. Upload those derivatives to a versioned prefix in the existing Supabase `product-images` bucket using the existing asset uploader. Use full public URLs in `images`; relative paths currently resolve to local `/product-images/` assets. Check every published URL before release.
6. Generate the final snapshot from the approved candidate. Test converter field mappings, duplicate detection, catalogue visibility and stock handling. Run `npm run products:validate` separately, since `npm run validate` does not include it. Run `npm run validate`, then preview mobile cards, categories, search, product pages, descriptions, SEO and cart totals without creating real orders.
7. Record the previous Worker version and catalogue for rollback. Deploy using the existing `npm run deploy` flow after release review. Verify the live domain against the approved manifest: expected product count, representative URLs, images, prices, stock, search and sitemap. Roll back if checks fail.

Supabase table synchronization is a separate optional consistency step, not the storefront publication mechanism. Inspect any consumers first, retain existing IDs, and avoid `--delete-missing` without an explicit retirement decision. No schema, auth, payment, webhook or deployment-configuration changes are required by this plan.

## Immediate next step

Prepare the candidate snapshot, duplicate-resolution report, old-to-new identity mapping and image manifest. These make the exact release reviewable before any upload or deployment. Final product count depends on duplicate resolution and whether the new set supplements or replaces the old catalogue.
