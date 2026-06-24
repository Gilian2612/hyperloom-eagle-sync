import requests
import os
import json
from pathlib import Path
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

EAGLE_API = os.getenv("EAGLE_API")
EAGLE_TOKEN = os.getenv("EAGLE_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = os.getenv("BUCKET")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
LIBRARY_PATH = None
SYNC_STATE_FILE = "sync_state.json"

def get_library_path():
    response = requests.get(f"{EAGLE_API}/api/library/info")
    data = response.json()
    return data.get("data", {}).get("library", {}).get("path", "")

def get_eagle_items():
    response = requests.get(f"{EAGLE_API}/api/item/list")
    data = response.json()
    return data.get("data", [])

def get_folder_map():
    response = requests.get(f"{EAGLE_API}/api/folder/list")
    data = response.json()
    folders = data.get("data", [])
    folder_map = {}
    
    def map_folders(folder_list):
        for folder in folder_list:
            folder_map[folder["id"]] = folder["name"]
            if folder.get("children"):
                map_folders(folder["children"])
    
    map_folders(folders)
    return folder_map

def get_item_path(item_id, name, ext):
    global LIBRARY_PATH
    if not LIBRARY_PATH:
        LIBRARY_PATH = get_library_path()
    file_path = Path(LIBRARY_PATH) / "images" / f"{item_id}.info" / f"{name}.{ext}"
    return str(file_path)

def is_already_synced(item_id):
    result = supabase.table("synced_assets").select("id").eq("id", item_id).execute()
    return len(result.data) > 0

def upload_to_supabase(file_path, item_id, filename):
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    path = f"{item_id}/{filename}"
    supabase.storage.from_(BUCKET).upload(path, file_bytes, {"upsert": "true"})
    public_url = supabase.storage.from_(BUCKET).get_public_url(path)
    return public_url

def save_metadata(item, public_url, folder_map):
    folder_ids = item.get("folders", [])
    folder_names = [folder_map.get(fid, fid) for fid in folder_ids]
    
    supabase.table("synced_assets").upsert({
        "id": item.get("id"),
        "name": item.get("name", ""),
        "ext": item.get("ext", ""),
        "tags": item.get("tags", []),
        "folders": folder_names,
        "width": item.get("width", 0),
        "height": item.get("height", 0),
        "size": item.get("size", 0),
        "public_url": public_url
    }).execute()

def get_last_sync_time():
    if Path(SYNC_STATE_FILE).exists():
        with open(SYNC_STATE_FILE, "r") as f:
            state = json.load(f)
            return state.get("last_sync", 0)
    return 0

def save_sync_time():
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump({"last_sync": int(datetime.now().timestamp() * 1000)}, f)

def get_item_mod_time(item):
    return item.get("lastModified", item.get("modificationTime", 0))

def sync():
    print("Obteniendo items de Eagle...")
    items = get_eagle_items()
    folder_map = get_folder_map()
    last_sync = get_last_sync_time()
    print(f"Encontrados {len(items)} items, {len(folder_map)} folders")
    print(f"Ultima sincronizacion: {datetime.fromtimestamp(last_sync / 1000) if last_sync else 'Nunca'}")
    
    synced = 0
    skipped = 0
    errors = 0
    
    for item in items:
        item_id = item.get("id")
        name = item.get("name", "sin_nombre")
        ext = item.get("ext", "")
        filename = f"{name}.{ext}"
        mod_time = get_item_mod_time(item)
        
        if mod_time <= last_sync and is_already_synced(item_id):
            skipped += 1
            continue
        
        file_path = get_item_path(item_id, name, ext)
        
        if not Path(file_path).exists():
            print(f"Archivo no encontrado: {filename}")
            errors += 1
            continue
        
        try:
            folder_ids = item.get("folders", [])
            folder_names = [folder_map.get(fid, fid) for fid in folder_ids]
            folder_str = " > ".join(folder_names) if folder_names else "Sin carpeta"
            print(f"Subiendo: {filename} [{folder_str}]")
            url = upload_to_supabase(file_path, item_id, filename)
            save_metadata(item, url, folder_map)
            print(f"OK: {url}")
            synced += 1
        except Exception as e:
            print(f"Error subiendo {filename}: {e}")
            errors += 1
    
    save_sync_time()
    print(f"\nResumen: {synced} subidos, {skipped} sin cambios, {errors} errores")

if __name__ == "__main__":
    sync()