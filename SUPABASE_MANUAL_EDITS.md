# Manual User Edits in Supabase

Yes, you can directly edit user subscriptions and playlist counts in Supabase! Here's how:

## Accessing the User Table

1. Go to your Supabase Dashboard
2. Navigate to **Table Editor**
3. Find and click on the `user` table

## Editing User Data

### To Change Subscription Plan:

1. Find the user row (search by email or ID)
2. Click on the `subscription_plan` column
3. Change the value to either:
   - `trial` - for free users (3 playlists/month)
   - `premium` - for paid users (25 playlists/month)

### To Change Number of Playlists:

1. Find the user row
2. Click on the `playlists_remaining` column
3. Enter the desired number (e.g., `0`, `3`, `25`, etc.)

## Using SQL Editor (Alternative Method)

You can also use the SQL Editor for bulk updates:

### Update a specific user's subscription:
```sql
UPDATE "user" 
SET subscription_plan = 'premium' 
WHERE id = 123;  -- Replace 123 with the user's ID
```

### Update a specific user's playlists:
```sql
UPDATE "user" 
SET playlists_remaining = 25 
WHERE id = 123;  -- Replace 123 with the user's ID
```

### Update by email:
```sql
UPDATE "user" 
SET subscription_plan = 'premium', playlists_remaining = 25 
WHERE email = 'user@example.com';
```

### Bulk update all users to premium:
```sql
UPDATE "user" 
SET subscription_plan = 'premium';
```

## Important Notes

- **Subscription Plan Values**: Must be exactly `trial` or `premium` (lowercase)
- **Playlists Remaining**: Can be any integer (0 or positive)
- **Monthly Limits**: The system checks monthly usage, but `playlists_remaining` can be used for manual overrides
- **Admins**: Admins automatically have premium access regardless of `subscription_plan` value

## Finding User IDs

To find a user's ID:
1. Search by email in the Table Editor
2. Or use SQL:
```sql
SELECT id, email, subscription_plan, playlists_remaining 
FROM "user" 
WHERE email = 'user@example.com';
```

