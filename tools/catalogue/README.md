# Local catalogue pipeline

This pipeline prepares review artifacts. It does not replace the active catalogue,
change product database rows, delete products, or deploy the Worker.

The session-confirmed commercial rules are recorded in `decisions.json`:
CSV prices are the final customer prices, and CSV inventory quantities are real.
VAT-exclusive prose is removed without changing the numeric prices. Input files
are read by column name, including UTF-8 BOM exports. Original photos are untouched.

## Prepare

Install the pinned dependencies with `python3 -m pip install -r tools/catalogue/requirements.txt`
(or use the existing project Python environment).

```bash
python3 tools/catalogue/prepare.py \
  --public-base https://qpopsroxrljpcryawmpb.supabase.co/storage/v1/object/public/product-images
```

Defaults use the supplied drop folders and write to `output/catalogue-review/`:

- `candidate-new.json`: all valid incoming rows, including unresolved duplicates.
- `candidate-release.json`: incoming rows with unresolved existing-product matches held out.
- `candidate-merged.json`: retained existing products plus `candidate-release.json`. Validate this before making it the storefront snapshot.
- `review.json`: policies, source checksum, rejected rows and duplicate groups.
- `duplicate-review.csv`: identifiers, prices, specifications and warranties side by side.
- `match-proposals.json` / `.csv`: suggested existing identities, with known configuration conflicts. Similarity is not an identity guarantee; CPU, generation, GPU, screen and other differences require review too.
- `existing-retained.json`: old products not explicitly matched for update.
- `image-manifest.json`: each source row's output key, SHA-256, dimensions and upscale flag.
- `images/catalogue-v1/`: content-addressed WebP derivatives, 1000×1000, white padding, no cropping or stretching. Smaller sources are upscaled and flagged; resizing cannot recover missing detail.

The November 2026 catalogue yielded 930 normalized incoming rows. The user
selected the KSh 42,000 Elite X2, confirmed final CSV prices and real stock
quantities, selected 12 months for the Lightwave power bank warranty, and asked
to hold products with unresolved existing matches. The prepared release
therefore contains 861 new listings plus the 245 retained existing listings;
69 incoming rows are held in the match report. The 891 count is distinct image
files, not product rows.

The storefront homepage now builds its category cards and deal filters from
categories present in the catalogue. Product snapshots preserve supplied stock
quantities and merchandising flags.

Output is gitignored. Images use SHA-256 names, so reruns do not overwrite a
published image with different bytes. Unreferenced files from previous runs may
remain locally, but the uploader reads only the current manifest.

## Resolve identities

Add explicit decisions under `rows`, keyed by `source_id`:

```json
{
  "ses:EXAMPLE:1": {"existing_slug": "existing-url-to-preserve"},
  "ses:EXAMPLE:2": {"slug": "distinct-configuration-slug", "sku": "DISTINCT-SKU", "keep_as_new": true},
  "ses:EXAMPLE:3": {"exclude": true, "reason": "Confirmed duplicate of ses:EXAMPLE:2"}
}
```

Use actual IDs from the review report; unknown IDs are rejected. Matching an old
slug replaces that row only in the candidate. Each old URL may be assigned once.
Do not merge stock quantities across duplicate source records without confirmation.
The generator always labels output as not ready to publish: it is a preparation
tool, not an automated release gate. Supplied compare-at prices also need review.

## Upload staged assets

Local integrity validation (no network):

```bash
node tools/catalogue/upload.mjs
```

Upload and verify public image bytes:

```bash
node --env-file-if-exists=.env --env-file-if-exists=.env.local tools/catalogue/upload.mjs --apply
```

This uses existing server-side credentials and the existing `product-images`
bucket. It verifies candidate URLs match the configured project, uploads missing
objects with overwrite disabled, verifies SHA-256 of public downloads, and writes
`upload-report.json`. Rerun to resume; verified existing objects are reused.
Uploading assets does not make product listings live.

## Before release

Resolve duplicate and match reports, inspect image/model correspondence, and
review the final product count. The current storefront adapter overrides stock
quantities with one and homepage selection with the first 24 rows; these must be
addressed when integrating the reviewed candidate. Keep checkout calculations,
auth, database schema and Worker configuration unchanged.

Run `npm run products:validate` after integrating the final snapshot, then
`npm run validate`. Catalogue pipeline tests are included in `npm test`.
Deploy only the reviewed release through the existing `npm run deploy` flow,
retaining the prior release for rollback. Pushing a commit to `main` also
starts the repository's Cloudflare deployment workflow.
