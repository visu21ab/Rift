# Stripe Setup Without CLI

You don't need Stripe CLI! Here's the simpler setup:

## Step 1: Create Stripe Account & Product ✅
1. Go to [stripe.com](https://stripe.com) and create account
2. Create product with 49 SEK/month recurring price
3. Copy your **Price ID** (starts with `price_...`)

## Step 2: Get API Keys ✅
1. Stripe Dashboard → **Developers** → **API keys**
2. Copy:
   - **Publishable key** (`pk_test_...`)
   - **Secret key** (`sk_test_...`)

## Step 3: Add to .env File

Add these to your `.env` file:

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...your_secret_key...
STRIPE_PUBLISHABLE_KEY=pk_test_...your_publishable_key...
STRIPE_PRICE_ID=price_...your_price_id...

# For webhook (we'll set this up when you deploy)
STRIPE_WEBHOOK_SECRET=
```

## Step 4: Test Locally (Without Webhooks)

For local testing, you can:
1. Test the checkout flow (users can subscribe)
2. Manually update users to premium in Supabase after payment
3. Webhooks will work automatically when you deploy to production

## Step 5: Set Up Webhook in Production

When you deploy your app (e.g., to Render, Heroku, etc.):

1. In Stripe Dashboard → **Developers** → **Webhooks**
2. Click **+ Add endpoint**
3. Set endpoint URL to: `https://your-domain.com/api/stripe-webhook`
4. Select these events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Copy the **Signing secret** (`whsec_...`)
6. Add it to your production environment variables:
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

## That's It!

Your app will work with subscriptions. The webhook will automatically upgrade users to premium when they pay, but for local testing, you can manually set users to `premium` in Supabase after testing checkout.

