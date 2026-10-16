-- Run once in your own Supabase project's SQL Editor.
-- Keep quota counters outside the public Data API schema.
CREATE SCHEMA IF NOT EXISTS nearby_eats;
REVOKE ALL ON SCHEMA nearby_eats FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS nearby_eats.api_usage (
    month text PRIMARY KEY CHECK (month ~ '^[0-9]{4}-[0-9]{2}$'),
    requests integer NOT NULL DEFAULT 0 CHECK (requests >= 0)
);
REVOKE ALL ON nearby_eats.api_usage FROM PUBLIC, anon, authenticated;
ALTER TABLE nearby_eats.api_usage ENABLE ROW LEVEL SECURITY;
