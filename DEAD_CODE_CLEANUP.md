# Dead Code Cleanup Report

Generated: 2026-01-26

## Summary
This document identifies unused code that can be safely removed from the codebase.

---

## 1. Legacy Graph Functions (Not Used)

### File: `app/graph.py`

**Dead Function: `build_graph()`**
- **Lines:** 7-39
- **Status:** Never called anywhere in codebase
- **Reason:** Replaced by `build_plotly_figure_json()` which uses `build_plotly_figure_from_db()`
- **Action:** DELETE

**Dead Function: `_db_to_legacy_rows()`**
- **Lines:** 44-82
- **Status:** Only called in commented-out code (line 169)
- **Reason:** Legacy function for old format, not used in current implementation
- **Action:** DELETE

**Dead Code Block: Commented `build_plotly_graph_json()`**
- **Lines:** 165-173
- **Status:** Commented out
- **Reason:** Old implementation replaced by current `build_plotly_figure_json()`
- **Action:** DELETE

---

## 2. Legacy Render Functions

### File: `app/plotly_graph/plotly_render.py`

**Dead Function: `build_maps()`**
- **Lines:** 13-80
- **Status:** Never called
- **Dependencies:** 
  - Uses `LegacyRow` from `legacy_io.py`
  - Uses `normalize_person` from `normalize.py`
- **Reason:** Replaced by `build_maps_from_db()` which works directly with database models
- **Action:** DELETE

**Dead Import: `LegacyRow`**
- **Line:** 7
- **Status:** Only used by dead `build_maps()` function
- **Action:** DELETE (after removing `build_maps`)

**Dead Import: `normalize_person`**
- **Line:** 8
- **Status:** Only used by dead `build_maps()` function
- **Action:** DELETE (after removing `build_maps`)

---

## 3. Duplicate build_plotly_figure_from_db Function

### File: `app/plotly_graph/plotly_render.py`

**Duplicate Function: Second `build_plotly_figure_from_db()`**
- **Lines:** 512-634
- **Status:** Duplicate/old implementation
- **Reason:** There are TWO functions with same name - one at line 151 (active) and one at line 512 (dead)
- **Action:** VERIFY which one is correct, DELETE the other
- **Note:** Line 151 version includes spouse positioning logic and dynamic spacing - appears to be the active one

---

## 4. Unused DB Plotly Module

### File: `app/plotly_graph/db_plotly.py`

**Entire File Status:** UNUSED
- **Size:** 245 lines
- **Function: `build_plotly_figure_from_db()`**
  - Different implementation than the one in `plotly_render.py`
  - Uses simpler layer layout
  - Import is commented out in `main.py` (line 15)
- **Functions:**
  - `_build_children_and_roots()` - lines 10-56
  - `_simple_layer_layout()` - lines 59-133
  - `build_plotly_figure_from_db()` - lines 136-245
- **Reason:** Old/alternate implementation replaced by `plotly_render.py` version
- **Action:** DELETE entire file OR keep as reference/backup (recommend delete)

---

## 5. Potentially Unused: Legacy IO Module

### File: `app/plotly_graph/legacy_io.py`

**Class: `LegacyRow`**
- **Lines:** 7-11
- **Status:** Still used by `_db_to_legacy_rows()` in `graph.py`
- **Dependencies:** Only `_db_to_legacy_rows()` which is unused
- **Action:** DELETE after removing `_db_to_legacy_rows()`

**Function: `read_legacy_file()`**
- **Lines:** 14-42
- **Status:** Never called
- **Reason:** CSV reading now handled by `family_tree_text.py`
- **Action:** DELETE

**Result:** Entire file can be deleted once dependent dead code is removed

---

## 6. Potentially Unused: Normalize Module

### File: `app/plotly_graph/normalize.py`

**Function: `normalize_person()`**
- **Lines:** 5-48
- **Status:** Only used by dead `build_maps()` function
- **Action:** DELETE entire file after removing `build_maps()`
- **Note:** Functionality replaced by person name handling in `family_tree_text.py`

---

## 7. Commented Out Imports

### File: `app/main.py`

**Dead Imports:**
- **Line 15:** `#from .plotly_graph.db_plotly import build_plotly_figure_from_db`
- **Line 16:** `#from .plotly_graph.plotly_render import build_plotly_figure_from_db`

**Action:** DELETE both commented lines

---

## 8. Unused Import in graph.py

### File: `app/graph.py`

**Dead Import: `LegacyRow`**
- **Line:** 4
- **Status:** Only used in `_db_to_legacy_rows()` which is dead
- **Action:** DELETE after removing `_db_to_legacy_rows()`

**Dead Import: `WorkingChange`**
- **Line:** 2
- **Status:** Never used in this file (WorkingChange is used in crud.py, not graph.py)
- **Action:** DELETE

---

## Cleanup Priority Order

### Phase 1: Safe Deletions (No Dependencies)
1. Delete commented code in `app/main.py` (lines 15-16)
2. Delete commented function in `app/graph.py` (lines 165-173)
3. Delete `build_graph()` function in `app/graph.py` (lines 7-39)
4. Delete unused `WorkingChange` import in `app/graph.py` (line 2)

### Phase 2: Legacy System Removal
5. Delete `_db_to_legacy_rows()` in `app/graph.py` (lines 44-82)
6. Delete `build_maps()` in `app/plotly_graph/plotly_render.py` (lines 13-80)
7. Delete entire `app/plotly_graph/normalize.py` file
8. Delete entire `app/plotly_graph/legacy_io.py` file
9. Remove `LegacyRow` import from `app/graph.py` (line 4)
10. Remove `normalize_person` and `LegacyRow` imports from `app/plotly_graph/plotly_render.py` (lines 7-8)

### Phase 3: Duplicate Resolution
11. **VERIFY** which `build_plotly_figure_from_db()` in `plotly_render.py` is active
12. Delete duplicate/old `build_plotly_figure_from_db()` (likely lines 512-634)

### Phase 4: Optional (Alternate Implementation)
13. Delete entire `app/plotly_graph/db_plotly.py` file (245 lines)

---

## Estimated Impact

- **Lines of code removed:** ~500-600 lines
- **Files removed:** 2-3 files (normalize.py, legacy_io.py, possibly db_plotly.py)
- **Risk level:** LOW (all identified code is confirmed unused)
- **Testing required:** Minimal (import tests, basic graph rendering)

---

## Verification Commands

Before deletion, verify nothing references these:

```bash
# Check for any usage of dead functions
grep -r "build_graph(" app/ --include="*.py"
grep -r "_db_to_legacy_rows" app/ --include="*.py"
grep -r "build_maps(" app/ --include="*.py"
grep -r "LegacyRow" app/ --include="*.py"
grep -r "normalize_person" app/ --include="*.py"
grep -r "db_plotly" app/ --include="*.py"
```

---

## Notes

1. **WorkingChange** is actively used for draft functionality - do NOT delete the model, only the unused import in graph.py
2. **build_plotly_figure_from_db** has two definitions - need to identify and remove the dead one
3. Keep the text importer (`family_tree_text.py`) - it's the active import system
4. The spouse positioning and dynamic spacing code (recently added) is in the active version
