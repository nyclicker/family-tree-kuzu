# Manual Testing Checklist

Use this checklist to manually verify the bug fixes before running automated tests.

## Context Menu Dismissal

- [ ] **Escape closes menu**: Right-click on a node/edge → Press Escape → Menu closes
- [ ] **Click closes menu**: Right-click to open menu → Left-click elsewhere → Menu closes  
- [ ] **Scroll closes menu**: Right-click to open menu → Scroll graph → Menu closes
- [ ] **Background right-click closes menu**: Open menu → Right-click on empty space → Menu closes (no new menu opens)

## Selection Behavior

- [ ] **Single node selection**: Click node A → Click node B → Only node B's subtree is highlighted
- [ ] **Single edge selection**: Click edge A → Click edge B → Only edge B is highlighted
- [ ] **Mixed selection**: Select node → Select edge → Only edge highlighted (node cleared)
- [ ] **Escape clears selection**: Select any node/edge → Press Escape → All highlights cleared

## Parent Pick Mode

- [ ] **Escape exits mode**: Right-click node → "Add Child Of" → Press Escape → Mode cancelled, status cleared
- [ ] **Background right-click exits**: Enter parent pick mode → Right-click background → Mode cancelled

## Edge Detection

- [ ] **Right-click on edge shows Delete Relationship**: Right-click directly on a relationship line → Menu shows "Delete Relationship" button
- [ ] **Edge hover works**: Move mouse over edge → Edge becomes detectable/hoverable

## Global Behavior

- [ ] **No duplicate listeners**: Interact with graph multiple times → Escape always works, no double-firing
- [ ] **No selection accumulation**: Click many nodes/edges → Graph doesn't accumulate extra traces/overlays
- [ ] **Menu always closes**: Every dismissal method (Escape/Click/Scroll/Background) reliably closes menu

## Expected Fixes

These issues should now be **FIXED**:

✅ Escape closes all context menus  
✅ Right-click on background closes menus (doesn't show "Add Person")  
✅ Selecting node/edge clears previous selection  
✅ Only one thing selected at a time  
✅ Global listeners don't duplicate on re-render

## How to Test

1. Start the server: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8888`
2. Open browser: http://localhost:8888
3. Load a tree with multiple nodes and relationships
4. Go through each checklist item systematically
5. Report any failures
