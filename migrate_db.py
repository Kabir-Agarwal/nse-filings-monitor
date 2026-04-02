"""
Run this script ONCE to add new columns to Supabase and create the subscribers table.
OR run these SQL commands in the Supabase SQL Editor (https://supabase.com/dashboard):

-- nse_filings columns:
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS exchange TEXT DEFAULT 'NSE';
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS confidence_pct INTEGER;
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS evidence TEXT;
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS action_window TEXT;

-- subscribers table:
CREATE TABLE IF NOT EXISTS subscribers (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    watchlist TEXT[] DEFAULT '{}',
    filing_types TEXT[] DEFAULT '{}',
    categories TEXT[] DEFAULT '{"HIGH"}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
"""
from dotenv import load_dotenv
load_dotenv()

import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

def check_column(table, col_name):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select={col_name}&limit=1",
        headers=headers, timeout=10
    )
    return r.status_code == 200

def check_table(table_name):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table_name}?limit=1",
        headers=headers, timeout=10
    )
    return r.status_code == 200

# ── Check nse_filings columns ─────────────────────────────────────────
columns_needed = {
    "exchange": "TEXT DEFAULT 'NSE'",
    "confidence_pct": "INTEGER",
    "evidence": "TEXT",
    "action_window": "TEXT",
}

print("Checking nse_filings columns...")
missing_cols = []
for col, col_type in columns_needed.items():
    exists = check_column("nse_filings", col)
    status = "EXISTS" if exists else "MISSING"
    print(f"  {col}: {status}")
    if not exists:
        missing_cols.append((col, col_type))

# ── Check subscribers table ───────────────────────────────────────────
print("\nChecking subscribers table...")
subscribers_exists = check_table("subscribers")
print(f"  subscribers: {'EXISTS' if subscribers_exists else 'MISSING'}")

# ── Print required SQL ────────────────────────────────────────────────
if not missing_cols and subscribers_exists:
    print("\n✅ All schema items exist. No migration needed.")
else:
    print(f"\n{'-' * 60}")
    print("Run the following SQL in Supabase SQL Editor:")
    print(">>  https://supabase.com/dashboard -> SQL Editor")
    print(f"{'-' * 60}\n")

    if missing_cols:
        print("-- Add missing nse_filings columns:")
        for col, col_type in missing_cols:
            print(f"ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS {col} {col_type};")
        print()

    if not subscribers_exists:
        print("-- Create subscribers table:")
        print("""CREATE TABLE IF NOT EXISTS subscribers (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    watchlist TEXT[] DEFAULT '{}',
    filing_types TEXT[] DEFAULT '{}',
    categories TEXT[] DEFAULT '{"HIGH"}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);""")

    print(f"\n{'-' * 60}")
    print("After running SQL, re-run this script to confirm.")
