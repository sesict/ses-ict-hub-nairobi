# Deploy the client storefront

See [deployment and cutover](deployment.md) for resource IDs, credentials, DNS and
certificate requirements. The current deployment target is the client Cloudflare
account `4b4295025db1d29a5f0a52288da307bb`.

```sh
npm run validate
npm run deploy
```

Local commands read `.env.client.local`; CI uses environment variables. Keep
`PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY`, `PUBLIC_FALLBACK_IMAGE_URL`,
`PUBLIC_TURNSTILE_SITE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `TURNSTILE_SECRET_KEY`,
`CLOUDFLARE_ACCOUNT_ID`, and `CLOUDFLARE_API_TOKEN` in the appropriate private file
or GitHub environment secrets. Never commit real credentials.

Deployment remains on workers.dev until the domain cutover checks are complete.
The GitHub Deploy workflow is manual during migration. Changing nameservers alone
is insufficient to guarantee uninterrupted TLS or reconcile new orders.
