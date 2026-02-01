# Toolbar Implementation - Visual Guide

## Toolbar Layout

```
┌─────────────────────────────────────────────────────────┐
│ Top-Right Corner (12px margin)                          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ➕ Add Person  │  🔗 Relationship  │  🔍 Search  │  ❓  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Pick Mode Indicator (when active):                    │
│  ┌───────────────────────────────────┐                 │
│  │ 👤 Click a person to be PARENT  ✕ │                 │
│  └───────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

## Button Functions

### 1. ➕ Add Person
- **Purpose**: Create a new person
- **Flow**:
  1. Click button
  2. Enter name in prompt
  3. Person added to tree
- **Visual**: Shows green confirmation

### 2. 🔗 Relationship
- **Purpose**: Link people together
- **Flow**:
  1. Right-click person (sets selection)
  2. Click button
  3. Choose relationship type:
     - "As CHILD" → Pick parent
     - "As PARENT" → Pick child
     - "As SPOUSE" → Pick spouse
  4. Click target person
- **Visual**: Indicator changes based on mode

### 3. 🔍 Search
- **Purpose**: Find people quickly
- **Flow**:
  1. Click button → Search modal opens
  2. Type person name
  3. Results appear (max 20)
  4. Click result to highlight in graph
- **Visual**: Live filtering + highlighting

### 4. ❓ Help
- **Purpose**: Show keyboard shortcuts & tips
- **Content**:
  - Toolbar button descriptions
  - Keyboard shortcuts (future)
  - Right-click menu tips
  - General usage guide

## Pick Mode Indicator

### States

**Hidden (Normal mode)**
```
No indicator visible - toolbar shows 4 buttons only
```

**Active (Pick mode)**
```
┌──────────────────────────────────────────────────┐
│ 👤 Click a person to be PARENT  ✕               │
├──────────────────────────────────────────────────┤
│ 👤 Click a person to be CHILD   ✕               │
├──────────────────────────────────────────────────┤
│ 👥 Click a person to be SPOUSE  ✕               │
└──────────────────────────────────────────────────┘
```

### How to Exit Pick Mode
1. **Click target person** → Completes relationship
2. **Press Escape** → Clears mode
3. **Click ✕ button** → Cancels mode
4. **Right-click background** → Cancels mode (existing behavior)

## Search Modal

```
┌──────────────────────────────────────┐
│ Search People                        │
├──────────────────────────────────────┤
│ ┌────────────────────────────────┐  │
│ │ Enter name to search... [∣]    │  │ ← autofocus
│ └────────────────────────────────┘  │
│                                      │
│ Search Results:                      │
│ ┌────────────────────────────────┐  │
│ │ John Smith                     │  │ ← clickable
│ │ Great-grandfather...           │  │
│ ├────────────────────────────────┤  │
│ │ Jane Smith                     │  │
│ │ No notes                       │  │
│ ├────────────────────────────────┤  │
│ │ (up to 20 results)             │  │
│ └────────────────────────────────┘  │
│                                      │
│              [Close]                 │
└──────────────────────────────────────┘
```

## Keyboard Integration

| Key | Action |
|-----|--------|
| Escape | Clear pick mode |
| (Future) Ctrl+N | New person |
| (Future) Ctrl+F | Search |
| (Future) Ctrl+R | Relationship |

## Color Scheme

```
Background:     #111 (Dark theme match)
Text:          #fff (White)
Border:        #333 (Subtle dark border)
Hover:         rgba(255,255,255,.08) (Light overlay)
Active:        rgba(255,255,255,.12) (Slightly lighter)
Pick Mode:     rgba(74,158,255,.15) (Blue tint)
```

## Responsive Behavior

### Desktop (1024px+)
✅ Full toolbar with labels and icons  
✅ Search modal centered on screen  

### Tablet (768px - 1023px)
⚠️ Toolbar may wrap (needs CSS refinement)  
- Toolbar positioned fixed top-right
- Buttons stack if needed

### Mobile (< 768px)
⚠️ Not yet optimized  
- Toolbar stays visible (potential overlap)
- **Future**: Convert to bottom sheet or hamburger menu

## Interaction Examples

### Example 1: Add a Person
```
1. Click "Add Person" button
2. Enter "Jane Doe" in prompt
3. Person appears in graph
4. Status: "Added person: Jane Doe"
```

### Example 2: Create Relationship
```
1. Right-click "John Smith" in graph
2. Click "Relationship" button
3. Choose "As CHILD"
4. Indicator: "👤 Click a person to be PARENT"
5. Click "Sarah Johnson"
6. Relationship created: "Sarah PARENT_OF John"
7. Indicator disappears
```

### Example 3: Search for Person
```
1. Click "Search" button
2. Type "John"
3. Results show:
   - John Smith
   - Johnny Doe
   - John's Brother
4. Click "John Smith"
5. Person highlighted 1.5x size in graph
6. Modal closes
```

## Benefits vs Previous UX

| Aspect | Before | After |
|--------|--------|-------|
| **Discoverability** | Hidden (must know to right-click) | Visible toolbar with labels |
| **Visual Feedback** | Text status only | Color indicator + visual highlight |
| **Add Person** | Right-click → "Add Person" | Direct button click |
| **Search** | Not available | Real-time search modal |
| **Help** | No guidance | Help button with shortcuts |
| **Affordance** | None (users confused) | Clear action buttons |

## Technical Details

- **Z-index**: 9998 (below modals/menus)
- **Position**: Fixed (stays visible while scrolling)
- **Performance**: O(n) search for < 10k people
- **Backward Compatibility**: 100% (no API changes)
- **Browser Support**: All modern browsers (ES6+)

## Next Steps for UX Improvements

### Phase 2 Features
- [ ] Keyboard shortcuts (Ctrl+N, Ctrl+F, Ctrl+R)
- [ ] Toast notifications (instead of status text)
- [ ] Undo/Redo buttons
- [ ] Simplified context menu with icons

### Phase 3 Polish
- [ ] Mobile-optimized toolbar (bottom sheet)
- [ ] Onboarding tooltips (first-time user)
- [ ] Drag-and-drop relationship creation
- [ ] Keyboard-only navigation
