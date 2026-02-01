# Test Coverage Assessment & Recommendations

**Generated**: January 31, 2026  
**Status**: Partial coverage with significant gaps in backend testing

---

## Current Test Coverage Overview

### ✅ What's Being Tested

| Layer | Coverage | Status |
|-------|----------|--------|
| **Frontend UI/UX** | ~40% | Good |
| **Frontend Import/Export** | ~30% | Partial |
| **Backend APIs** | ~5% | Critical Gap |
| **Backend Business Logic** | ~0% | Critical Gap |
| **Database Layer** | ~0% | Critical Gap |
| **Integration Tests** | ~5% | Minimal |

### Test Statistics

- **Total Test Files**: 5 (3 unit, 2 e2e)
- **Unit Tests**: ~55 specs (mostly placeholder stubs)
- **E2E Tests**: ~30 specs (browser-based interactions)
- **Backend Tests**: 0 Python tests
- **Coverage Tools Configured**: Jest (no coverage reporting), Playwright

---

## Current Test Breakdown

### Frontend Unit Tests (`tests/unit/`)
**Location**: [tests/unit/](tests/unit/)  
**Status**: ⚠️ Mostly placeholder stubs

#### context-menu.test.js (~45 lines)
- 7 test suites with placeholder tests
- **Issue**: All tests are tautological (`expect(true).toBe(true)`)
- **Coverage**: 0% (needs implementation)
- **Scope**: Menu functions, selection, handlers, parent-pick mode, edge detection

#### import-export.test.js (~450 lines)
- 24 passing tests for export/import functionality
- **Focus Areas**:
  - ✅ Export data structure validation (5 tests)
  - ✅ Filename generation logic (5 tests)
  - ✅ Version management (5 tests)
  - ✅ Data validation (5 tests)
  - ✅ Import payload structure (4 tests)
- **Coverage**: ~40% of import/export client-side logic
- **Issue**: No actual API calls tested, only structure validation

#### importer-formats.test.js (~360 lines)
- 35+ format validation tests
- **Coverage Areas**:
  - ✅ Text/CSV format detection
  - ✅ CSV parsing and compatibility
  - ✅ JSON format validation
  - ✅ Person/relationship record fields
- **Coverage**: ~35% of format handling
- **Issue**: Mock-based, doesn't test actual import pipeline

### Frontend E2E Tests (`tests/e2e/`)
**Location**: [tests/e2e/](tests/e2e/)  
**Status**: ✅ Solid UI/UX coverage

#### ui-interactions.spec.js (~380 lines)
- 20+ end-to-end interaction tests
- **Coverage Areas**:
  - ✅ Context menu behavior (Escape, click, scroll, right-click dismissal)
  - ✅ Node selection and highlighting
  - ✅ Edge selection and highlighting
  - ✅ Parent pick mode workflows
  - ✅ Tree and draft management
  - ✅ Graph rendering
- **Coverage**: ~45% of frontend interactions
- **Strengths**: Tests real browser behavior via Playwright
- **Issue**: Limited coverage of error states, edge cases

#### bug-fixes.spec.js (~200 lines)
- 12 targeted tests for recent fixes
- **Focus**: Menu dismissal, selection clearing, listener binding
- **Coverage**: ~30% (regression tests only)

#### import-export.spec.js (~335 lines)
- 15+ tests for import/export workflows
- **Coverage**:
  - ✅ Export endpoint JSON structure
  - ✅ Tree metadata inclusion
  - ✅ File download behavior
  - ✅ Save-to-disk functionality
  - ✅ Version history cleanup
- **Coverage**: ~40% of import/export workflows
- **Issue**: Limited error scenario testing

### Backend (Python)
**Status**: ❌ **ZERO test coverage**

- ❌ No FastAPI endpoint tests
- ❌ No CRUD operation tests
- ❌ No database model tests
- ❌ No import/parse logic tests
- ❌ No versioning logic tests
- ❌ No graph rendering tests

---

## Critical Gaps Analysis

### 🔴 Critical (Must Address)

| Gap | Impact | Files Affected |
|-----|--------|-----------------|
| **No Python backend tests** | Medium risk - bugs propagate to prod | `app/main.py`, `app/crud.py`, `app/models.py` |
| **No API integration tests** | Medium risk - frontend/backend desync | All FastAPI routes |
| **No database tests** | Medium risk - data corruption, lost relationships | `app/db.py`, `app/models.py` |
| **No import parsing tests** | High risk - data loss/corruption on import | `app/importers/*` |
| **Placeholder unit tests** | Low risk but misleading | `tests/unit/context-menu.test.js` |

### 🟡 High Priority (Should Add)

| Gap | Impact | Severity |
|-----|--------|----------|
| Error handling/validation | Bugs in edge cases | Medium |
| Tree versioning logic | Incorrect active version logic | Medium |
| Duplicate detection | Silent failures | Medium |
| Graph layout rendering | Performance issues | Low |
| Name parsing edge cases | Data corruption | High |
| Relationship constraints | Invalid data states | High |

### 🟠 Medium Priority (Nice to Have)

| Gap | Impact |
|-----|--------|
| Performance/load tests | Scalability unknown |
| Accessibility tests | WCAG compliance unknown |
| Cross-browser E2E tests | Only Chromium tested |
| API response time tests | Latency unknown |

---

## Recommended Test Folder Structure

### Proposed Organization

```
tests/
├── README.md                          # Testing guide
├── setup.js                           # Jest setup
├── teardown.js                        # Cleanup
├── jest.config.js
├── playwright.config.js
│
├── unit/                              # JavaScript unit tests (frontend)
│   ├── ui/
│   │   ├── context-menu.test.js      # NOW: REAL tests (not placeholders)
│   │   ├── graph-selection.test.js   # NEW: Selection logic
│   │   └── event-handlers.test.js    # NEW: Global handlers
│   ├── utils/
│   │   ├── import-export.test.js     # Existing (rename from root)
│   │   └── importer-formats.test.js  # Existing (rename from root)
│   └── fixtures/
│       └── sample-trees.js            # NEW: Test data
│
├── integration/                       # JavaScript integration (frontend+API)
│   ├── import-workflow.test.js        # NEW: Full import cycle
│   ├── tree-versioning.test.js        # NEW: Version management
│   └── graph-data-flow.test.js        # NEW: Data synchronization
│
├── e2e/                               # Playwright browser tests
│   ├── README.md                      # E2E test guide
│   ├── ui/
│   │   ├── ui-interactions.spec.js   # Existing
│   │   ├── error-scenarios.spec.js   # NEW: Error handling
│   │   └── accessibility.spec.js     # NEW: A11y compliance
│   ├── workflows/
│   │   ├── import-export.spec.js     # Existing
│   │   ├── tree-creation.spec.js     # NEW: Create/edit trees
│   │   └── relationship-editing.spec.js # NEW: CRUD operations
│   ├── regression/
│   │   └── bug-fixes.spec.js         # Existing
│   └── fixtures/
│       └── test-data.json             # Shared test data
│
├── backend/                           # Python backend tests (NEW)
│   ├── README.md                      # Backend test guide
│   ├── conftest.py                    # NEW: Pytest fixtures
│   ├── unit/
│   │   ├── test_crud.py              # NEW: CRUD operations
│   │   ├── test_models.py            # NEW: Model validation
│   │   ├── test_schemas.py           # NEW: Pydantic schemas
│   │   ├── test_importers.py         # NEW: Import parsing
│   │   └── test_graph.py             # NEW: Graph rendering
│   ├── integration/
│   │   ├── test_import_workflow.py   # NEW: Full import pipeline
│   │   ├── test_versioning.py        # NEW: Version constraints
│   │   └── test_duplicate_detection.py # NEW: Dedup logic
│   └── api/
│       ├── test_people_routes.py     # NEW: /people endpoints
│       ├── test_relationships_routes.py # NEW: /relationships
│       ├── test_import_routes.py     # NEW: /import endpoint
│       └── test_export_routes.py     # NEW: /export endpoint
│
├── fixtures/                          # Shared test data
│   ├── sample-trees.json              # Tree with various structures
│   ├── large-tree.json                # Performance testing
│   └── edge-cases.json                # Name variations, nulls
│
├── MANUAL_TEST_CHECKLIST.md          # Existing
├── TESTING.md                         # Existing (update with structure)
└── TEST_SUITE_SUMMARY.md             # Existing (update counts)
```

---

## Test Implementation Roadmap

### Phase 1: Foundation (Week 1)
**Goal**: Establish backend testing infrastructure

- [ ] Create `tests/backend/` directory structure
- [ ] Add `conftest.py` with pytest fixtures for DB, session management
- [ ] Set up test database (isolated from production)
- [ ] Create `fixtures/sample-trees.json` with test data
- [ ] Add pytest + dependencies to `requirements.txt`
- [ ] Configure GitHub Actions CI to run all test suites

**Files to Create**:
```python
tests/backend/conftest.py                 # 40-60 lines
tests/backend/unit/test_models.py         # 80-120 lines
tests/backend/unit/test_schemas.py        # 60-100 lines
tests/backend/api/test_people_routes.py   # 100-150 lines
```

### Phase 2: Core Backend Coverage (Week 2)
**Goal**: 50%+ Python test coverage for critical paths

- [ ] Write CRUD operation tests
- [ ] Write import/parsing tests (text, JSON formats)
- [ ] Write tree versioning tests
- [ ] Write relationship constraint tests
- [ ] Write duplicate detection tests

**Target**: ~150 new Python tests

### Phase 3: Frontend Unit Tests (Week 3)
**Goal**: Replace placeholder tests with real implementations

- [ ] Replace `context-menu.test.js` placeholder tests (need to extract functions from `app.js`)
- [ ] Create `ui/graph-selection.test.js`
- [ ] Create `ui/event-handlers.test.js`
- [ ] Create `utils/import-export.test.js` (move & expand)
- [ ] Refactor `app.js` for testability (export pure functions)

**Strategy**: Extract logic from `app.js` into testable modules

### Phase 4: Integration Tests (Week 4)
**Goal**: Cross-layer communication coverage

- [ ] Create `integration/import-workflow.test.js` (frontend calls API)
- [ ] Create `backend/integration/test_import_workflow.py` (full pipeline)
- [ ] Create `e2e/workflows/tree-creation.spec.js` (end-to-end)
- [ ] Create `e2e/error-scenarios.spec.js` (error handling)

### Phase 5: Coverage Metrics & CI (Week 5+)
**Goal**: Automated coverage reporting

- [ ] Add Jest coverage reporting (`--coverage` flag)
- [ ] Add Pytest coverage reporting (`pytest-cov`)
- [ ] Configure GitHub Actions to report coverage
- [ ] Set coverage thresholds (80% backend, 60% frontend)
- [ ] Generate coverage badges for README

---

## Priority Test Cases to Add

### Backend (Immediate)

**CRUD Operations** (`tests/backend/unit/test_crud.py`)
```python
def test_create_person_with_tree_version()
def test_list_people_filters_by_active_version()
def test_create_relationship_with_earliest_ancestor_null_to_person()
def test_enforce_one_earliest_ancestor_per_version()
def test_create_relationship_validates_to_person_required()
def test_create_tree_version_increments_number()
def test_active_flag_updates_on_new_version()
```

**Import Pipeline** (`tests/backend/integration/test_import_workflow.py`)
```python
def test_import_txt_creates_new_tree()
def test_import_txt_creates_new_version_if_tree_exists()
def test_import_json_with_duplicate_detection()
def test_import_with_relationship_normalization()
def test_import_with_complex_name_parsing()
def test_import_creates_earliest_ancestor_root()
```

**Error Handling** (`tests/backend/api/test_import_routes.py`)
```python
def test_import_unsupported_file_format_returns_400()
def test_import_malformed_json_returns_400()
def test_import_missing_required_fields_returns_400()
def test_import_circular_relationships_detected()
def test_export_nonexistent_tree_returns_404()
```

### Frontend (High Priority)

**E2E Error Scenarios** (`tests/e2e/ui/error-scenarios.spec.js`)
```javascript
test('Import with invalid file shows error message')
test('Network error during export shows retry option')
test('Duplicate name detection shows merge dialog')
test('Circular relationship prevents creation')
```

**Real Unit Tests** (`tests/unit/ui/context-menu.test.js`)
```javascript
// Extract functions from app.js, then:
test('dismissAllMenus removes all menu elements')
test('clearSelectionHighlights removes all traces')
test('getNodeAtPoint returns correct node object')
```

---

## Configuration Updates Required

### jest.config.js
```javascript
// Add coverage collection
collectCoverageFrom: [
  'web/**/*.js',
  '!web/app.js',  // Refactor first
],
coverageThreshold: {
  global: {
    branches: 60,
    functions: 60,
    lines: 60,
    statements: 60,
  },
},
```

### playwright.config.js
```javascript
// Add webServer for auto-start, better timeouts
webServer: {
  command: 'python -m uvicorn app.main:app --port 8080',
  port: 8080,
  reuseExistingServer: false,
},
timeout: 30000,
```

### package.json
```json
{
  "scripts": {
    "test": "jest --coverage",
    "test:watch": "jest --watch",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:all": "npm run test && npm run test:e2e",
    "test:coverage": "jest --coverage && echo 'Coverage report in coverage/'"
  }
}
```

### requirements.txt
```
# Add for backend tests
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-xdist>=3.3.0  # Parallel test execution
httpx>=0.24.0        # For testing async endpoints
```

---

## Critical Next Steps

1. **Create `tests/backend/` structure** (2 hours)
   - Minimal setup with conftest.py and one test file
   
2. **Write 10-15 critical backend tests** (1 day)
   - CRUD basics, import pipeline, constraints
   
3. **Add pytest to CI/CD** (1 hour)
   - GitHub Actions: run tests on push
   
4. **Refactor `app.js` for testability** (1 day)
   - Extract pure functions, export for testing
   
5. **Replace placeholder unit tests** (4 hours)
   - Implement real assertions

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| **Backend Test Coverage** | 0% | 70%+ |
| **Total Python Tests** | 0 | 100+ |
| **Frontend Unit Tests** | 7 placeholders | 30+ real tests |
| **E2E Test Suite** | 30+ | 50+ |
| **API Endpoint Coverage** | 0% | 80%+ |
| **CRUD Operation Coverage** | 0% | 90%+ |

---

## Files Needing Refactoring for Testability

| File | Issue | Solution |
|------|-------|----------|
| `web/app.js` | Monolithic, hard to unit test | Extract functions: `dismissAllMenus()`, `getNodeAtPoint()`, etc. |
| `app/importers/*.py` | Import functions work but not tested | Create test fixtures with sample data |
| `app/crud.py` | Business logic untested | Create unit tests with mocked Session |
| `app/models.py` | Constraints unstated in code | Add pydantic validators, test them |

---

## Related Documentation

- [Current TESTING.md](TESTING.md) - Update with new folder structure
- [Current TEST_SUITE_SUMMARY.md](TEST_SUITE_SUMMARY.md) - Update counts
- [Current MANUAL_TEST_CHECKLIST.md](MANUAL_TEST_CHECKLIST.md) - Keep as-is, reference in README
- **NEW**: Backend testing guide (to create)
- **NEW**: Test data fixtures guide (to create)

---

## Summary Table: What's Tested vs. What's Not

| Component | Current | Needed |
|-----------|---------|--------|
| **UI Context Menus** | ✅ E2E | ✅ Unit (extract from app.js) |
| **UI Selection** | ✅ E2E | ✅ Unit |
| **Import/Export API** | ✅ E2E | ⚠️ API tests needed |
| **Text Import Parser** | ⚠️ Format validation only | ❌ Full pipeline |
| **JSON Import Parser** | ⚠️ Structure validation only | ❌ Full pipeline |
| **Duplicate Detection** | ❌ | ❌ CRITICAL |
| **Tree Versioning** | ❌ | ❌ CRITICAL |
| **CRUD Operations** | ❌ | ❌ CRITICAL |
| **Graph Rendering** | ✅ E2E visual | ❌ Logic/algorithms |
| **Database Constraints** | ❌ | ❌ CRITICAL |
| **Error Handling** | ❌ | ❌ HIGH |

