const fs = require('fs');
const path = require('path');

const config = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));

const SUPABASE_URL = config.supabase_url;
const SUPABASE_KEY = config.supabase_key;
const BUCKET = config.bucket;
const SYNC_INTERVAL = config.sync_interval_ms;

let lastSyncTime = 0;

async function getEagleItems() {
    const response = await fetch('http://localhost:41595/api/item/list');
    const data = await response.json();
    return data.data || [];
}

async function getLibraryPath() {
    const response = await fetch('http://localhost:41595/api/library/info');
    const data = await response.json();
    return data.data?.library?.path || '';
}

async function getFolderMap() {
    const response = await fetch('http://localhost:41595/api/folder/list');
    const data = await response.json();
    const map = {};
    function mapFolders(folders) {
        for (const folder of folders) {
            map[folder.id] = folder.name;
            if (folder.children) mapFolders(folder.children);
        }
    }
    mapFolders(data.data || []);
    return map;
}

async function isAlreadySynced(itemId) {
    const response = await fetch(
        `${SUPABASE_URL}/rest/v1/synced_assets?id=eq.${itemId}&select=id`,
        { headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` } }
    );
    const data = await response.json();
    return data.length > 0;
}

async function uploadToSupabase(filePath, itemId, filename) {
    const fileBytes = fs.readFileSync(filePath);
    const storagePath = `${itemId}/${filename}`;
    
    await fetch(`${SUPABASE_URL}/storage/v1/object/${BUCKET}/${storagePath}`, {
        method: 'POST',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`,
            'Content-Type': 'image/png',
            'x-upsert': 'true'
        },
        body: fileBytes
    });
    
    return `${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/${storagePath}`;
}

async function saveMetadata(item, publicUrl, folderMap) {
    const folderNames = (item.folders || []).map(id => folderMap[id] || id);
    
    await fetch(`${SUPABASE_URL}/rest/v1/synced_assets`, {
        method: 'POST',
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates'
        },
        body: JSON.stringify({
            id: item.id,
            name: item.name || '',
            ext: item.ext || '',
            tags: item.tags || [],
            folders: folderNames,
            width: item.width || 0,
            height: item.height || 0,
            size: item.size || 0,
            public_url: publicUrl
        })
    });
}

async function sync() {
    try {
        console.log('[Hyperloom] Starting sync...');
        const items = await getEagleItems();
        const folderMap = await getFolderMap();
        const libraryPath = await getLibraryPath();
        
        let synced = 0;
        let skipped = 0;
        
        for (const item of items) {
            const modTime = item.lastModified || item.modificationTime || 0;
            
            if (modTime <= lastSyncTime && await isAlreadySynced(item.id)) {
                skipped++;
                continue;
            }
            
            const filename = `${item.name}.${item.ext}`;
            const filePath = path.join(libraryPath, 'images', `${item.id}.info`, filename);
            
            if (!fs.existsSync(filePath)) continue;
            
            const url = await uploadToSupabase(filePath, item.id, filename);
            await saveMetadata(item, url, folderMap);
            synced++;
            console.log(`[Hyperloom] Synced: ${filename}`);
        }
        
        lastSyncTime = Date.now();
        console.log(`[Hyperloom] Done — ${synced} synced, ${skipped} skipped`);
    } catch (err) {
        console.error('[Hyperloom] Sync error:', err);
    }
}

eagle.onPluginCreate(async () => {
    console.log('[Hyperloom] Plugin started');
    await sync();
    setInterval(sync, SYNC_INTERVAL);
});