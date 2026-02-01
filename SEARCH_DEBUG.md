# Search Debug Guide

## If Search Still Throws an Error

Follow these steps to identify the exact issue:

### Step 1: Open DevTools Console
1. Press **F12** 
2. Click **Console** tab
3. You should see any error messages in RED

### Step 2: Check What Error You See
Look for error messages that contain:
- "tree_id" → Tree not loaded properly
- "HTTP" → API request failed
- "undefined" → Variable not initialized
- "Cannot read property" → Accessing null/undefined

### Step 3: Copy the Exact Error
Report the **exact error message** from the console. Examples:
- "Cannot read property 'customdata' of undefined"
- "HTTP 404: not found"
- "activeTreeId is not defined"

### Step 4: Check Browser Network Tab
1. Click **Network** tab in DevTools
2. Try search again
3. Look for requests to `/people`
4. Check the response:
   - Green ✅ = Success (200)
   - Red ❌ = Error (404, 500, etc.)
   - Click request to see response data

### Step 5: Verify Tree is Loaded
In Console, type:
```javascript
console.log('activeTreeId:', activeTreeId)
console.log('activeTreeVersionId:', activeTreeVersionId)
```

If both show `null`, the tree isn't loaded yet. Try:
1. Reload page
2. Wait for graph to render
3. Then try search

## Common Fixes

### "No tree loaded" Message
- Wait a few seconds for tree to load
- Refresh page (Ctrl+F5)
- Check if any tree exists in left panel

### API Error (HTTP 404, 500)
- API might have crashed
- Try restarting: `docker compose restart api`
- Check logs: `docker compose logs api --tail 20`

### JavaScript Error (undefined)
- This was a bug in the code
- The latest fix should resolve it
- Hard refresh: Ctrl+Shift+R
- If persists, clear browser cache

## Quick Test After Fix

1. Open http://localhost:8080
2. Wait for graph to load
3. Click 🔍 Search button
4. Type first letter of a name
5. Results should appear OR
6. Error message should be clear (not cryptic)

If you still see errors, share:
- **Exact error message** (copy from console)
- **Browser type** (Chrome, Firefox, Safari)
- **System** (Windows, Mac, Linux)

That will help debug faster!
