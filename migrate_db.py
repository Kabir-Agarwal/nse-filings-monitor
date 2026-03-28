"""
Run this script ONCE to add new columns to Supabase.
OR run these SQL commands in the Supabase SQL Editor (https://supabase.com/dashboard):

ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS exchange TEXT DEFAULT 'NSE';
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS confidence_pct INTEGER;
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS evidence TEXT;
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS action_window TEXT;
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

def check_column(col_name):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/nse_filings?select={col_name}&limit=1",
        headers=headers, timeout=10
    )
    return r.status_code == 200

columns_needed = {
    "exchange": "TEXT DEFAULT 'NSE'",
    "confidence_pct": "INTEGER",
    "evidence": "TEXT",
    "action_window": "TEXT",
}

print("Checking Supabase columns...")
missing = []
for col, col_type in columns_needed.items():
    exists = check_column(col)
    status = "EXISTS" if exists else "MISSING"
    print(f"  {col}: {status}")
    if not exists:
        missing.append((col, col_type))

if not missing:
    print("\nAll columns exist. No migration needed.")
else:
    print(f"\n{len(missing)} column(s) missing. Please run this SQL in Supabase SQL Editor:")
    print("-" * 60)
    for col, col_type in missing:
        print(f"ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS {col} {col_type};")
    print("-" * 60)
    print("\nGo to: https://supabase.com/dashboard -> SQL Editor -> paste & run")
