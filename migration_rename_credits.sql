-- Migration script to rename credits_remaining to playlists_remaining
-- Run this in your Supabase SQL Editor

-- Rename the column
ALTER TABLE "user" RENAME COLUMN credits_remaining TO playlists_remaining;

-- Verify the change
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'user' AND column_name = 'playlists_remaining';

