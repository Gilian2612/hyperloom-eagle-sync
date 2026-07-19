# Eagle → Supabase Sync

Script that syncs assets from a local Eagle library to Supabase Storage, preserving metadata, folder structure, and generating permanent public URLs.

## Setup

1. Install dependencies:
pip install supabase requests python-dotenv

2. Create a `.env` file with:

EAGLE_API=http://localhost:41595

EAGLE_TOKEN=your_eagle_api_token

SUPABASE_URL=your_supabase_project_url

SUPABASE_KEY=your_supabase_service_role_key

BUCKET=eagle-assets

3. Make sure Eagle is open before running.


## Usage Notes

python eagle_sync.py

The script will:
- Detect your Eagle library automatically
- Upload new/modified assets to Supabase Storage
- Save metadata (name, tags, folders, dimensions, size) to the `synced_assets` table
- Skip already synced files
- Generate permanent public URLs for each asset

## How it works

- First run: syncs everything
- Subsequent runs: only syncs new or modified files since last run
- Moving a file to a folder updates its metadata in Supabase
- To force a full resync, delete `sync_state.json`

## Requirements

- Python 3.10+
- Eagle 4.0+
- Supabase project with `eagle-assets` storage bucket and `synced_assets` table
