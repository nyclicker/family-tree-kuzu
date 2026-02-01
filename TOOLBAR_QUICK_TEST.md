# Quick Testing Guide - Toolbar Implementation

## Start Here

The API is running at **http://localhost:8080** and already has test data loaded.

### What You'll See
- Existing tree with 1000+ people already imported
- Left panel: Tree & version controls (unchanged)
- **TOP-RIGHT: NEW TOOLBAR** with 4 buttons
  - ➕ Add Person
  - 🔗 Relationship  
  - 🔍 Search
  - ❓ Help

---

## Quick Test Flow (5 minutes)

### Step 1: Verify Toolbar Visibility
1. Open http://localhost:8080 in browser
2. Look at **top-right corner**
3. You should see a dark box with 4 buttons
4. If visible ✅ → Move to Step 2

**If NOT visible** ❌:
- Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R)
- Check browser DevTools Console (F12) for errors

### Step 2: Test Search Feature
**This is the most important new feature**

1. Click the 🔍 **Search** button
2. A modal pops up in center of screen
3. Type a person's name (e.g., "John" or "Smith")
4. Results appear below search box (real-time)
5. Click a result
6. Modal closes
7. Person should be highlighted in graph (larger node)

✅ **Pass**: Results appear, click works, person highlighted  
❌ **Fail**: No results, modal doesn't close, person not highlighted

### Step 3: Test Add Person
1. Click the ➕ **Add Person** button
2. A prompt appears: "Enter person name:"
3. Type "Test Person Jane"
4. Click OK
5. Graph updates
6. Left panel status shows "Added person: Test Person Jane"

✅ **Pass**: Person appears in graph  
❌ **Fail**: Graph doesn't update or error shown

### Step 4: Test Pick Mode Indicator
**This shows visual feedback while creating relationships**

1. Right-click any person in the graph
2. Click the 🔗 **Relationship** button (top-right toolbar)
3. A small menu appears with 3 options:
   - ➕ As CHILD
   - ➕ As PARENT
   - 💕 As SPOUSE
4. Click "As CHILD"
5. Look at toolbar - you'll see a **blue indicator**:
   - "👤 Click a person to be PARENT"
6. Click another person in the graph
7. Relationship created!
8. Blue indicator disappears

✅ **Pass**: Indicator shows and disappears  
❌ **Fail**: No indicator or relationship not created

### Step 5: Test Help System
1. Click the ❓ **Help** button (far right toolbar)
2. An alert appears with usage guide
3. Contains sections:
   - TOOLBAR BUTTONS
   - KEYBOARD SHORTCUTS
   - RIGHT-CLICK MENU
   - RELATIONSHIPS
   - Tips

✅ **Pass**: Alert appears with content  
❌ **Fail**: No alert or content missing

### Step 6: Test Escape Key (Quick Feature)
1. Right-click a person
2. Click Relationship button
3. Choose "As PARENT"
4. Blue indicator appears
5. **Press Escape key**
6. Indicator should disappear

✅ **Pass**: Indicator disappears  
❌ **Fail**: Indicator stays or error

---

## Expected Behavior

### Toolbar Button Locations
```
┌─────────────────────────────────────────┐
│                                         │
│  ➕ Add Person   🔗 Relationship   🔍 Search  ❓  │ ← TOP RIGHT
│                                         │
└─────────────────────────────────────────┘
```

### Pick Mode Indicator (Active)
```
┌────────────────────────────────────────────┐
│  👤 Click a person to be PARENT  ✕         │ ← BLUE BACKGROUND
└────────────────────────────────────────────┘
```

### Search Modal
```
┌─────────────────────────────┐
│ Search People              │
├─────────────────────────────┤
│ [Enter name to search...]   │
├─────────────────────────────┤
│ John Smith                  │ ← clickable
│ Notes preview...            │
├─────────────────────────────┤
│ Jane Doe                    │
│ Notes preview...            │
└─────────────────────────────┘
```

---

## Console Check (Important!)

While testing, check the browser console for errors:

1. Press **F12** to open DevTools
2. Click **Console** tab
3. You should see NO RED ERROR messages
4. Some BLUE INFO messages are OK

**If you see red errors**, note them and let me know exactly what they say.

---

## Test Results Template

After testing, fill this in:

```
✅ Toolbar visible?                 YES / NO / (describe issue)
✅ Search results appear?            YES / NO / (describe issue)
✅ Click search result works?        YES / NO / (describe issue)
✅ Add Person button works?          YES / NO / (describe issue)
✅ Pick mode indicator shows?        YES / NO / (describe issue)
✅ Escape key clears mode?           YES / NO / (describe issue)
✅ Help button shows alert?          YES / NO / (describe issue)
✅ No console errors?                YES / NO / (list errors if any)

Any other issues?
_________________________________________________________________
_________________________________________________________________

Ready for Phase 2?                   YES / NO / (conditional)
```

---

## Troubleshooting

### "Toolbar not visible"
```
1. Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
2. Check DevTools Console (F12) for errors
3. If errors: Copy error messages and share
4. If no errors: Try different browser
```

### "Search doesn't work"
```
1. Make sure you're typing in the search modal
2. Modal should autofocus the input field
3. Type slowly and wait for results
4. If still nothing, check Console for errors
```

### "Relationship didn't create"
```
1. Make sure you right-clicked a person first
2. The context menu should appear
3. Then click "Relationship" button
4. Choose relationship type from submenu
5. Then click target person
6. Check Console for errors
```

### "Pick mode indicator doesn't appear"
```
1. Make sure you're in pick mode (selected Relationship)
2. Indicator should be BLUE with text
3. It replaces the normal toolbar display
4. Check Console for errors
```

---

## Next Steps

### If ALL tests pass ✅
You're ready for Phase 2! We can add:
- Keyboard shortcuts (Ctrl+N, Ctrl+F, etc.)
- Toast notifications
- Undo/Redo
- More features

### If SOME tests fail ⚠️
Let me know which ones and any error messages. I can:
- Fix bugs
- Adjust styling
- Improve functionality

### If MAJOR issues 🔴
Don't worry! Let's:
1. Note what's broken
2. Check console errors
3. Test in different browser
4. Debug systematically

---

## Tips for Testing

- **Test in Chrome first** (most stable)
- **Start with search** (easiest to verify)
- **Try different trees** (if multiple available)
- **Test with large/small names** (edge cases)
- **Watch the graph update** (visual feedback)
- **Check status bar** (left side text updates)

---

**Ready?** Open http://localhost:8080 and start with Step 1! 🚀

Let me know how it goes with results or any issues you encounter.
