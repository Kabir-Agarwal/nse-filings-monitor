"""
Run this script ONCE to add new columns to Supabase and create the subscribers table.

Auto-creates tables when SUPABASE_PAT is set in .env:
  SUPABASE_PAT=sbp_xxxx  (from https://supabase.com/dashboard/account/tokens)

OR run these SQL commands manually in the Supabase SQL Editor:
  https://supabase.com/dashboard -> SQL Editor

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
SUPABASE_PAT = os.environ.get("SUPABASE_PAT", "")  # Personal Access Token from dashboard

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PROJECT_REF = SUPABASE_URL.replace("https://", "").split(".")[0]


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


def execute_sql_via_management_api(sql: str) -> tuple[bool, str]:
    """Execute SQL via Supabase Management API (requires SUPABASE_PAT in .env)."""
    if not SUPABASE_PAT:
        return False, "SUPABASE_PAT not set"
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    r = requests.post(
        url,
        json={"query": sql},
        headers={"Authorization": f"Bearer {SUPABASE_PAT}", "Content-Type": "application/json"},
        timeout=15,
    )
    if r.status_code in (200, 201):
        return True, "OK"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


# -- Check nse_filings columns ---------------------------------------------
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

# -- Check subscribers table -----------------------------------------------
print("\nChecking subscribers table...")
subscribers_exists = check_table("subscribers")
print(f"  subscribers: {'EXISTS' if subscribers_exists else 'MISSING'}")

# -- Auto-create via Management API if PAT is available --------------------
if (missing_cols or not subscribers_exists) and SUPABASE_PAT:
    print(f"\nSUPABASE_PAT found - attempting auto-migration via Management API...")

    if missing_cols:
        for col, col_type in missing_cols:
            sql = f"ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS {col} {col_type};"
            ok, msg = execute_sql_via_management_api(sql)
            print(f"  ADD COLUMN {col}: {'OK' if ok else 'FAIL'} {msg}")

    if not subscribers_exists:
        sql = """CREATE TABLE IF NOT EXISTS subscribers (
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
);"""
        ok, msg = execute_sql_via_management_api(sql)
        print(f"  CREATE TABLE subscribers: {'OK' if ok else 'FAIL'} {msg}")

    # Re-check after migration
    print("\nRe-checking after migration...")
    for col in columns_needed:
        exists = check_column("nse_filings", col)
        print(f"  {col}: {'EXISTS' if exists else 'MISSING'}")
    subscribers_exists = check_table("subscribers")
    print(f"  subscribers: {'EXISTS' if subscribers_exists else 'MISSING'}")

# -- Print required SQL if still missing -----------------------------------
still_missing_cols = [c for c in columns_needed if not check_column("nse_filings", c)]
still_missing_sub = not check_table("subscribers")

if not still_missing_cols and not still_missing_sub:
    print("\nAll schema items exist. No migration needed.")
else:
    if not SUPABASE_PAT:
        print("\nTip: Add SUPABASE_PAT=sbp_xxxx to .env for auto-migration.")
        print("     Get your token: https://supabase.com/dashboard/account/tokens\n")

    print(f"\n{'-' * 60}")
    print("Run the following SQL in Supabase SQL Editor:")
    print(">>  https://supabase.com/dashboard -> SQL Editor")
    print(f"{'-' * 60}\n")

    if still_missing_cols:
        print("-- Add missing nse_filings columns:")
        for col in still_missing_cols:
            print(f"ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS {col} {columns_needed[col]};")
        print()

    if still_missing_sub:
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
