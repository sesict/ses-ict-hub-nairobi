# Client Cloudflare deployment and domain cutover

The storefront deploys as an Astro Cloudflare Worker. The client repository is
`git@github.com:sesict/ses-ict-hub-nairobi.git`.

## Client resources

- Account: `4b4295025db1d29a5f0a52288da307bb`
- Zone: `f1b6d3e1359d5c5837ce547c0da54ccc` (`sesicthub.co.ke`)
- Worker: `ses-hub-superbase-stack-app`
- Preview: `https://ses-hub-superbase-stack-app.sesicthub224.workers.dev`
- Redirect Worker: `ses-ict-hub-www-redirect`
- Supabase: `https://qpopsroxrljpcryawmpb.supabase.co`

`wrangler.jsonc` initially has no custom-domain routes. Deploying this configuration
updates only the client preview. The original account and nameservers remain intact.
The client SESSION namespaces are defined in both Wrangler configurations.

## Credentials and build

Copy `.env.example` to `.env.client.local`, which is ignored by Git. The command
wrapper parses this file without executing shell content. Explicit environment
variables take precedence. It checks the client account and Supabase URL.
Do not copy migration backups, access tokens, service keys, or customer exports into Git.

Required values:

- `PUBLIC_SUPABASE_URL`
- `PUBLIC_SUPABASE_ANON_KEY` (publishable key)
- `PUBLIC_FALLBACK_IMAGE_URL`
- `PUBLIC_TURNSTILE_SITE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (server only)
- `TURNSTILE_SECRET_KEY` (server only)
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Use a client token with Workers Scripts Edit, Workers KV Storage Edit, Workers
Routes Edit, Zone Read, Zone Settings Edit, DNS Edit, SSL and Certificates Edit,
and Turnstile Edit on the intended account/zone. The migration additionally needs
DNS Read on the source zone to export all records accurately.

```sh
npm ci
npm run validate
npm run cf:whoami
npm run deploy
bash scripts/deploy-www-redirect.sh
```

Worker runtime secrets must be uploaded separately with `wrangler secret bulk`,
using a private JSON file containing only application values (never the deployment
API token). Public values must also be present during the build. Keep private
values out of client bundles. Configure Supabase Auth's site URL and redirect allow
list for the production URL and the explicit preview callback URL.

## GitHub Actions

CI validates pushes and pull requests. Deployment is manually dispatched while the
domain migration is pending. Configure the `production` environment with the public
build values and Cloudflare credentials listed above before running Deploy. The workflow uploads the six application bindings, including the two private runtime
keys, from the production environment using a temporary private file. Other existing
Worker secrets are preserved. Git SSH access alone cannot configure GitHub Actions secrets; use repository Settings
or an authenticated GitHub CLI. The client production environment has been configured. Container publishing remains a separate workflow.

## Domain cutover: not ready until all checks pass

The client's assigned nameservers are `ullis.ns.cloudflare.com` and
`wesley.ns.cloudflare.com`. Do not change delegation merely because a preview works.

1. Export source DNS with the API or dashboard and compare every record in the client
   zone, including MX, SPF, DKIM, DMARC, CAA and verification records. Do not copy
   Cloudflare proxy IP addresses from public DNS discovery as origin addresses.
2. Check DNSSEC at the registrar and source zone. Remove the old DS configuration
   before changing nameservers if DNSSEC is enabled. Confirm no source zone hold.
3. Verify the preview: catalogue images, account pages, server API configuration,
   Turnstile, and expected redirects. Confirm any external payment, messaging or
   email-provider credentials and webhooks separately.
4. Reconcile any customers/orders added to the live source since the database copy.
   A snapshot is not continuous replication; plan the final write handoff before
   customers can place orders against both databases.
5. Resolve certificate readiness. Cloudflare reissues certificates after account
   moves. A pending zone cannot proxy traffic, and Worker custom domains require an
   active zone. The Free plan staging workflow does not guarantee zero downtime.
   If uninterrupted TLS is mandatory, arrange Cloudflare's prevalidated certificate
   approach before scheduling the move; paid certificate products are not enabled
   automatically by this project.
6. At the agreed cutover, update the registrar delegation, wait for the client zone
   to become Active, then attach the Worker domains:

   ```sh
   bash scripts/attach-apex-domain.sh
   bash scripts/deploy-www-redirect.sh --attach
   ```

   Both commands refuse to attach while the client zone is pending. The apex command
   records the production route in `wrangler.jsonc`; validate, commit and push that
   change so later deployments retain the route.
7. Verify valid HTTPS on apex and www, path/query-preserving www redirects, DNS/mail,
   sign-in, images and checkout before declaring cutover complete. Re-enable DNSSEC
   with the client's DS values only after the new delegation is stable.

Retain the old deployment and private database backups until verification is complete.
Reverting nameservers is not an instant rollback because resolvers cache delegation.

References: [Cloudflare account moves](https://developers.cloudflare.com/fundamentals/manage-domains/move-domain/),
[Worker custom domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).
