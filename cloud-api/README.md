# VibeBridge cloud-api

Minimal Stripe-backed licensing for VibeBridge Pro. No database: license state
lives entirely on the Stripe Customer object (`metadata.vibebridge_device_token`),
checked live against Stripe on every status request. Same Stripe account as
Autofill, separate Product/Price and separate Vercel project/billing surface.

## Routes

- `POST /api/checkout` — `{deviceToken}` → creates a Stripe Checkout session
  (subscription, 14-day trial) and returns `{url}`.
- `POST /api/stripe-webhook` — Stripe webhook. Tags the resulting Customer
  with the device token from `checkout.session.completed`.
- `GET /api/license-status?token=<deviceToken>` — `{active, status, trialEnd,
  currentPeriodEnd}`, read live from Stripe.

## Required environment variables (Vercel project settings)

- `STRIPE_SECRET_KEY` — same Stripe account as Autofill, but this project
  should use its own restricted key if you want to scope it down.
- `STRIPE_WEBHOOK_SECRET` — signing secret for *this* project's webhook
  endpoint (create a new webhook endpoint in Stripe pointed at
  `https://<this-deployment>/api/stripe-webhook`; do not reuse Autofill's).
- `VIBEBRIDGE_PRICE_ID` — `price_1URNYSCqEsT2Knpa73ALTJm6` (VibeBridge Pro,
  $9/month).
- `CHECKOUT_SUCCESS_URL` / `CHECKOUT_CANCEL_URL` — where Stripe redirects
  after checkout. A simple static page is enough; the extension polls
  `license-status` independently rather than relying on the redirect.

## Deploy

```bash
cd cloud-api
vercel link   # new project, e.g. vibebridge-cloud-api
vercel env add STRIPE_SECRET_KEY production
vercel env add STRIPE_WEBHOOK_SECRET production
vercel env add VIBEBRIDGE_PRICE_ID production
vercel env add CHECKOUT_SUCCESS_URL production
vercel env add CHECKOUT_CANCEL_URL production
vercel --prod
```

After the first deploy, create the Stripe webhook endpoint pointed at the
deployed `/api/stripe-webhook` URL, then set `STRIPE_WEBHOOK_SECRET` from the
signing secret Stripe shows for that endpoint and redeploy.
