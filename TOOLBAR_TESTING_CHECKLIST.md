# Toolbar Testing Checklist

## Pre-Test Setup
- [ ] API running (localhost:8080)
- [ ] Frontend loaded without errors
- [ ] Import a test tree (optional, for full testing)

## Test 1: Toolbar Visibility & Layout
**Expected**: Toolbar visible in top-right corner with 4 buttons
- [ ] Toolbar appears at top-right
- [ ] Buttons visible: ➕ Add Person
- [ ] Buttons visible: 🔗 Relationship
- [ ] Buttons visible: 🔍 Search
- [ ] Buttons visible: ❓ Help
- [ ] Pick mode indicator hidden (initially)
- [ ] Dark theme styling matches left panel
- [ ] No console errors

**How to test**:
```
1. Open http://localhost:8080
2. Check top-right corner for toolbar
3. Open browser DevTools (F12)
4. Check Console tab for errors
```

## Test 2: Add Person Button
**Expected**: Creates new person via prompt
- [ ] Click "Add Person" button
- [ ] Prompt appears asking for name
- [ ] Enter "Test Person"
- [ ] Confirm prompt
- [ ] Person added to graph
- [ ] Status bar shows success message
- [ ] No console errors

**Pass/Fail**: ___________

## Test 3: Search Button
**Expected**: Opens search modal with live filtering
- [ ] Click "Search" button
- [ ] Modal opens in center of screen
- [ ] Search input focused (cursor visible)
- [ ] Type a person name
- [ ] Results appear (max 20)
- [ ] Results show name + notes
- [ ] Click result
- [ ] Modal closes
- [ ] Person highlighted in graph (larger node)
- [ ] Status shows selected person

**Test with person names**:
```
If tree is empty, Add Person first:
1. Add "John Smith"
2. Add "Jane Doe"
3. Search for "john"
4. Should find "John Smith"
5. Click result
6. Graph should highlight the node
```

**Pass/Fail**: ___________

## Test 4: Relationship Button (No Selection)
**Expected**: Shows alert if no person selected
- [ ] Click "Relationship" button (without right-clicking)
- [ ] Alert appears: "Please right-click a person first..."
- [ ] Close alert
- [ ] No errors

**Pass/Fail**: ___________

## Test 5: Relationship Button (With Selection)
**Expected**: Shows menu with 3 relationship types
- [ ] Right-click a person in graph
- [ ] Person is selected (context menu appears)
- [ ] Click "Relationship" button
- [ ] Submenu appears with options:
  - ➕ As CHILD
  - ➕ As PARENT
  - 💕 As SPOUSE
- [ ] Menu closes after 5 seconds (or click outside)

**Pass/Fail**: ___________

## Test 6: Pick Mode - Parent Flow
**Expected**: Pick mode indicator shows and relationship created
- [ ] Right-click "John Smith" (or other person)
- [ ] Click "Relationship" button
- [ ] Choose "As CHILD"
- [ ] Indicator appears: "👤 Click a person to be PARENT"
- [ ] Indicator has blue background
- [ ] Indicator has close button (✕)
- [ ] Click another person (e.g., "Jane Doe")
- [ ] Relationship created
- [ ] Indicator disappears
- [ ] Status shows: "Added: John CHILD_OF Jane"

**Pass/Fail**: ___________

## Test 7: Pick Mode - Child Flow
**Expected**: Pick mode indicator for child relationship
- [ ] Right-click "Jane Doe"
- [ ] Click "Relationship" button
- [ ] Choose "As PARENT"
- [ ] Indicator appears: "👤 Click a person to be CHILD"
- [ ] Click target person
- [ ] Relationship created
- [ ] Indicator disappears

**Pass/Fail**: ___________

## Test 8: Pick Mode - Spouse Flow
**Expected**: Pick mode indicator for spouse relationship
- [ ] Right-click a person
- [ ] Click "Relationship" button
- [ ] Choose "As SPOUSE"
- [ ] Indicator appears: "👥 Click a person to be SPOUSE"
- [ ] Click target person
- [ ] Relationship created
- [ ] Indicator disappears

**Pass/Fail**: ___________

## Test 9: Pick Mode Cancel - Close Button
**Expected**: Clicking close button clears mode
- [ ] Enter any pick mode (As CHILD, As PARENT, or As SPOUSE)
- [ ] Indicator appears with close button (✕)
- [ ] Click close button (✕)
- [ ] Indicator disappears
- [ ] Subtree highlighting removed
- [ ] No error messages

**Pass/Fail**: ___________

## Test 10: Pick Mode Cancel - Escape Key
**Expected**: Pressing Escape clears mode
- [ ] Enter any pick mode
- [ ] Indicator visible
- [ ] Press Escape key
- [ ] Indicator disappears
- [ ] Subtree highlighting removed
- [ ] No error messages

**Pass/Fail**: ___________

## Test 11: Help Button
**Expected**: Shows comprehensive help alert
- [ ] Click "?" button
- [ ] Alert appears with content including:
  - "TOOLBAR BUTTONS:" section
  - "KEYBOARD SHORTCUTS:" section
  - "RIGHT-CLICK MENU:" section
  - "RELATIONSHIPS:" section
  - "Tips:" section
- [ ] Content is readable
- [ ] Can close alert

**Pass/Fail**: ___________

## Test 12: Right-Click Menu Still Works
**Expected**: Context menu unaffected by toolbar
- [ ] Right-click a person
- [ ] Original context menu appears:
  - ✏️ Edit Person…
  - 🔗 Add CHILD_OF relationship…
  - 🔗 Add PARENT_OF relationship…
  - 💕 Add SPOUSE_OF relationship…
  - 🗑️ Delete Person
- [ ] Click "Edit Person"
- [ ] Edit modal opens
- [ ] Make a change and save
- [ ] Change persists

**Pass/Fail**: ___________

## Test 13: Search Modal Close
**Expected**: Modal closes properly
- [ ] Click "Search" button
- [ ] Modal opens
- [ ] Click "Close" button
- [ ] Modal closes
- [ ] Toolbar still visible

**Alternative close methods**:
- [ ] Press Escape (if implemented)
- [ ] Click backdrop (dark area outside modal)

**Pass/Fail**: ___________

## Test 14: Edge Cases
**Expected**: Graceful handling of errors

### Empty Tree
- [ ] Load fresh tree with no people
- [ ] Click "Add Person"
- [ ] Add one person
- [ ] Search for that person
- [ ] Should find it

**Pass/Fail**: ___________

### Special Characters in Names
- [ ] Add person with name: "John O'Brien"
- [ ] Search for "O'Brien"
- [ ] Should find without issues
- [ ] HTML not rendered (no XSS)

**Pass/Fail**: ___________

### Long Names
- [ ] Add person with very long name (50+ chars)
- [ ] Search for partial name
- [ ] Results display correctly
- [ ] Modal doesn't overflow

**Pass/Fail**: ___________

### No Results
- [ ] Open search
- [ ] Type "ZZZZZZZZ" (unlikely to exist)
- [ ] Should show "No people found"
- [ ] No errors

**Pass/Fail**: ___________

## Test 15: Performance
**Expected**: Toolbar operations are fast

### Search Performance
- [ ] Measure search response time
- [ ] Should find results in < 1 second
- [ ] Even with 100+ people

**Pass/Fail**: ___________

### Graph Updates
- [ ] Add person via toolbar
- [ ] Graph updates immediately
- [ ] No lag or freezing

**Pass/Fail**: ___________

## Test 16: Browser Console
**Expected**: No errors or warnings
- [ ] Open DevTools (F12)
- [ ] Go to Console tab
- [ ] Perform all tests above
- [ ] Check for red errors
- [ ] Check for yellow warnings
- [ ] Should be clean (no toolbar-related errors)

**Errors found**: ___________

**Pass/Fail**: ___________

## Test 17: Cross-Browser (if available)
- [ ] Chrome/Edge: ___________
- [ ] Firefox: ___________
- [ ] Safari: ___________

## Test 18: Responsive (Desktop)
**Expected**: Toolbar usable at different screen sizes

### 1920px (Desktop)
- [ ] Toolbar fully visible
- [ ] All buttons readable
- [ ] No overlap with graph

**Pass/Fail**: ___________

### 1280px (Laptop)
- [ ] Toolbar fully visible
- [ ] All buttons readable
- [ ] No overlap with tree bar

**Pass/Fail**: ___________

### 768px (Tablet)
- [ ] Toolbar still visible
- [ ] Buttons might wrap (acceptable for Phase 3)
- [ ] Still functional

**Pass/Fail**: ___________

## Summary

### Overall Status
- **Total Tests**: 18+
- **Passed**: ___/18
- **Failed**: ___/18
- **Pass Rate**: ___%

### Critical Issues Found
```
1. ___________
2. ___________
3. ___________
```

### Minor Issues / Polish Needed
```
1. ___________
2. ___________
3. ___________
```

### Ready for Phase 2?
- [ ] Yes, all tests passed
- [ ] No, need fixes first
- [ ] Partially, some tests need work

### Notes
```
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________
```

---

## How to Run These Tests

### Manual Testing (Recommended first)
1. Load app at http://localhost:8080
2. Work through Test 1-18 in order
3. Note pass/fail for each
4. Document any issues

### Automated Testing (Future Phase 3)
These tests could be automated with Playwright:
- Test 1: Element visibility checks
- Test 2-18: User interaction flows
- Test 16: Console error detection
- Test 17-18: Responsive design checks

## Test Data Suggestions

If starting fresh, create this test data:
```
Person 1: "John Smith" (Notes: "Founder")
Person 2: "Jane Doe" (Notes: "John's spouse")
Person 3: "James Smith" (Notes: "John's son")
Person 4: "Mary Johnson" (Notes: "James's wife")

Then create relationships:
- Jane SPOUSE_OF John
- James CHILD_OF John and Jane
- Mary SPOUSE_OF James
```

This gives you a small tree to test relationships and search.
