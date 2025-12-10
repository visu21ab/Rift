# How to Find Your Stripe Price ID

## The Difference
- **Product ID** (starts with `prod_...`) - This is the product itself
- **Price ID** (starts with `price_...`) - This is what you need for subscriptions

## Method 1: From Products Page

1. Go to **Products** in your Stripe Dashboard
2. Click on your product (e.g., "Rift Premium")
3. You'll see the product details page
4. Look for the **Pricing** section
5. Under the price, you'll see a **Price ID** that starts with `price_...`
6. Click on it or copy it

## Method 2: If You Only See Product ID

If you created a product but don't see a Price ID, you need to add pricing:

1. Go to **Products** → Click your product
2. Click **Add another price** or **Edit pricing**
3. Set:
   - **Price**: 49.00 SEK
   - **Billing period**: Monthly (recurring)
4. Click **Save**
5. The Price ID will appear (starts with `price_...`)

## Method 3: Using Stripe Dashboard API

1. Go to **Developers** → **API keys**
2. Use the test mode toggle to ensure you're in test mode
3. Go to **Products** → Your product
4. The Price ID should be visible in the pricing section

## Quick Check

Your Price ID should look like:
- `price_1234567890abcdef` (test mode)
- `price_abcdef1234567890` (live mode)

If you only see `prod_...`, you need to add pricing to your product first!

