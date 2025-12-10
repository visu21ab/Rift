# Stripe Subscription Setup Guide

This guide will help you set up Stripe payments for your Rift application.

## Overview

The application now supports:
- **Trial Plan**: 3 free playlists per month
- **Premium Plan**: 25 playlists per month for 49 SEK/month

## Step 1: Create a Stripe Account

1. Go to [https://stripe.com](https://stripe.com) and create an account
2. Complete the account setup (you can use test mode for development)

## Step 2: Get Your Stripe API Keys

1. Log in to your Stripe Dashboard
2. Go to **Developers** → **API keys**
3. Copy your **Publishable key** and **Secret key** (use test keys for development)

## Step 3: Create a Product and Price in Stripe

1. In Stripe Dashboard, go to **Products**
2. Click **+ Add product**
3. Set up the product:
   - **Name**: Rift Premium
   - **Description**: Monthly subscription for 25 playlists per month
   - **Pricing model**: Standard pricing
   - **Price**: 49.00 SEK
   - **Billing period**: Monthly (recurring)
4. Click **Save product**
5. Copy the **Price ID** (starts with `price_...`)

## Step 4: Set Up Webhook Endpoint

1. In Stripe Dashboard, go to **Developers** → **Webhooks**
2. Click **+ Add endpoint**
3. Set the endpoint URL to: `https://your-domain.com/api/stripe-webhook`
   - For local development, use Stripe CLI (see below)
4. Select events to listen to:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Click **Add endpoint**
6. Copy the **Signing secret** (starts with `whsec_...`)

## Step 5: Configure Environment Variables

Add these to your `.env` file:

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...  # Your Stripe secret key (use sk_test_ for test mode)
STRIPE_PUBLISHABLE_KEY=pk_test_...  # Your Stripe publishable key (use pk_test_ for test mode)
STRIPE_WEBHOOK_SECRET=whsec_...  # Your webhook signing secret
STRIPE_PRICE_ID=price_...  # The Price ID from Step 3
```

## Step 6: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install the `stripe` package.

## Step 7: Database Migration

The User model has been updated with new fields:
- `stripe_customer_id` - Stores Stripe customer ID
- `stripe_subscription_id` - Stores Stripe subscription ID
- `subscription_plan` - Now defaults to 'trial' instead of 'free'

Run your database migrations or the tables will be created automatically on first run.

## Step 8: Test the Integration (Local Development)

For local development, use Stripe CLI to forward webhooks:

1. Install Stripe CLI: https://stripe.com/docs/stripe-cli
2. Login: `stripe login`
3. Forward webhooks: `stripe listen --forward-to localhost:5000/api/stripe-webhook`
4. Copy the webhook signing secret from the CLI output and use it in your `.env`

## Step 9: Test Payments

1. Use Stripe test card numbers:
   - Success: `4242 4242 4242 4242`
   - Any future expiry date (e.g., 12/34)
   - Any 3-digit CVC
   - Any ZIP code

2. Test the flow:
   - Create a playlist (should work 3 times on trial)
   - Click "Subscribe to Premium"
   - Complete checkout with test card
   - Verify subscription status updates
   - Create more playlists (should allow up to 25)

## Production Deployment

1. Switch to live mode in Stripe Dashboard
2. Update environment variables with live keys:
   - `STRIPE_SECRET_KEY=sk_live_...`
   - `STRIPE_PUBLISHABLE_KEY=pk_live_...`
3. Update webhook endpoint URL to your production domain
4. Update `APP_BASE_URL` in `.env` to your production URL

## Important Notes

- The webhook endpoint must be publicly accessible (Stripe needs to reach it)
- Use HTTPS in production (required by Stripe)
- The webhook secret is different for test and live modes
- Monthly limits reset automatically based on the calendar month
- Users can cancel subscriptions, which will downgrade them to trial at period end

## Troubleshooting

- **Webhook not working**: Check that the endpoint is publicly accessible and the signing secret is correct
- **Subscription not updating**: Check webhook logs in Stripe Dashboard
- **Payment fails**: Verify your Stripe account is activated and can accept payments
- **Database errors**: Ensure the new User model fields are added to your database

## API Endpoints

- `POST /api/create-checkout-session` - Creates Stripe checkout session
- `POST /api/cancel-subscription` - Cancels user's subscription
- `POST /api/stripe-webhook` - Handles Stripe webhook events (called by Stripe)

