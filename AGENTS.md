# SES E-Commerce Storefront (Production Maintenance)

## Core Guidelines
- **Mobile-First & UI**: Build mobile-first. Maintain SES brand aesthetics (clean spacing, rounded cards, dark navy text, SES blue buttons).
- **Product Presentation**: Product cards display square 1000x1000px images. Show clean specs (CPU, RAM, storage) where available. Use "Refurbished" instead of "Refurb" and "In Stock" instead of "Stock". Do not duplicate discount/savings copy.
- **Cart & Contact**: Keep Add to Cart and WhatsApp floating actions accessible and non-intrusive.

## Production Guardrails
- **Logic Invariants**: Do not alter checkout, payment, cart, order calculation, auth, Supabase schemas, webhooks, or Cloudflare Worker deployment configs unless explicitly requested.
- **Quality Gates**: Always run `npm run validate` (or `npm run lint && npm run test`) before completing any task.
