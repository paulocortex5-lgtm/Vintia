# Paddle Billing Setup

Vantia uses **Paddle as the Merchant of Record**: Vantia never stores card
data, and Paddle handles tax collection, refunds and compliance. This guide
covers account creation, product setup, environment variables and webhook
wiring.

> Paddle replaced Stripe in master prompt v6.0 (§B). No Stripe code, config,
> dependency or database table may remain in the repo (R56).

## 1. Create the account (10 min)

1. Sign up at <https://paddle.com/signup> and choose **Sandbox** for
   development — sandbox transactions never move real money.
2. Go to **Settings → API Keys** and generate an **API key**. Copy it to
   `PADDLE_API_KEY`.
3. Go to **Settings → Notification Destinations** and add a destination:
   - URL: `https://vantia-engine.onrender.com/api/paddle/webhook`
   - Events: `transaction.completed`, `transaction.payment_failed`,
     `subscription.created`, `subscription.canceled`, `customer.created`
   - Copy the **destination secret** to `PADDLE_WEBHOOK_SECRET`.

Paddle retries any delivery that does not return `200` within **5 seconds**,
so the webhook route answers immediately after recording the event row
(§G.7, R51).

## 2. Create the three products (5 min)

In **Products → New product**, create three **one-time** products:

| Product name           | Price  | Pack id      | Price env var           | Credits granted |
|------------------------|--------|--------------|-------------------------|-----------------|
| Vantia 10K Credits     | $5.00  | `pack_10k`   | `PADDLE_PRICE_PACK_10K` | 10,000          |
| Vantia 50K Credits     | $20.00 | `pack_50k`   | `PADDLE_PRICE_PACK_50K` | 50,000          |
| Vantia 250K Credits    | $80.00 | `pack_250k`  | `PADDLE_PRICE_PACK_250K`| 250,000         |

For each price, copy the **price id** (`pri_xxxxxxxxxxxxxxxx`) into the
matching env var. Price ids are environment-specific: sandbox price ids do
**not** work against the production API and vice versa.

## 3. Environment variables

Add these to Render (backend) — they are already listed in `.env.example`
with `REPLACE_ME` placeholders:

```
PADDLE_API_KEY=REPLACE_ME
PADDLE_CLIENT_TOKEN=REPLACE_ME
PADDLE_WEBHOOK_SECRET=REPLACE_ME
PADDLE_ENVIRONMENT=sandbox
PADDLE_PRICE_PACK_10K=REPLACE_ME
PADDLE_PRICE_PACK_50K=REPLACE_ME
PADDLE_PRICE_PACK_250K=REPLACE_ME
NEXT_PUBLIC_PADDLE_CLIENT_TOKEN=REPLACE_ME
NEXT_PUBLIC_PADDLE_ENVIRONMENT=sandbox
```

`PADDLE_CLIENT_TOKEN` is the **browser-side** token (Settings → API Keys →
client-side token). Only the two `NEXT_PUBLIC_*` vars belong on Vercel; the
rest are server-side only (R60).

## 4. How a purchase flows

```
User → /credits/purchase → clicks Buy
  → POST /api/credits/checkout {pack_id}          (backend)
  → engine.credits.paddle_client.create_checkout_transaction(...)
  → returns transaction.checkout.url
  → Paddle Checkout overlay opens
  → user pays
  → POST /api/paddle/webhook (transaction.completed)
  → engine.credits.paddle_webhook.handle_webhook(...)
       1. verify Paddle-Signature (HMAC-SHA256 over "<ts>:<body>", 5s window)
       2. idempotency check: SELECT from paddle_events WHERE event_id = ?
       3. ledger.topup_from_paddle(user_id, credits, event_id)
       4. upsert paddle_events row (source of truth, R58)
  → user lands on /credits?success=1
```

`custom_data` carries `{user_id, pack_id, credits}` through the transaction
so the webhook can attribute the credit without any lookup.

## 5. Event handling

| Event                    | Action                                                    |
|--------------------------|-----------------------------------------------------------|
| `transaction.completed`  | Credit the balance (from `custom_data.credits`)          |
| `transaction.payment_failed` | Record the event for audit; do not credit           |
| `subscription.created`   | Update the tier in `profiles` (if subscriptions are used)|
| `subscription.canceled`  | Downgrade the tier after the period ends                |
| `customer.created`       | Store `paddle_customer_id` in `paddle_customers`         |

## 6. Verify locally

```bash
pip install -r requirements.txt   # includes paddle-python-sdk
pytest tests/test_paddle_webhook.py -v
```

The webhook tests exercise the signature check and the duplicate-event
no-op without any network access. Live-mode requires real sandbox keys,
which are unavailable until a Paddle account exists — mark those steps as
blocked rather than stubbing fake keys (R13).

## 7. Going live

1. In Paddle, upgrade from Sandbox to Production.
2. Recreate the three products/prices in production and copy the new price
   ids over the sandbox ones.
3. Regenerate the API key and client token; set `PADDLE_ENVIRONMENT=production`.
4. Set `PADDLE_ENVIRONMENT=production` on Render **and**
   `NEXT_PUBLIC_PADDLE_ENVIRONMENT=production` on Vercel.
5. Confirm the notification destination points at the production URL.
6. Buy a pack with a test card and check `/credits` shows the new balance.