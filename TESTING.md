# Family Tree - Automated Testing Guide

## Quick Start

### Backend Tests (Python)
```bash
# Install dependencies
pip install -e .
pip install pytest pytest-cov

# Run backend tests
pytest tests/backend/ -v

# Run with coverage report
pytest tests/backend/ --cov=app --cov-report=html
```

### Frontend Tests (JavaScript)
```bash
# 1. Install dependencies
npm install
npx playwright install chromium

# 2. Start the backend server (in separate terminal)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8888

# 3. Run tests
npm test                    # Unit tests with coverage
npm run test:e2e           # E2E tests only  
npm run test:all           # All tests
./tests/run-all-tests.sh   # All tests (comprehensive)
```

## What's Been Fixed

Recent UX improvements with automated test coverage:

### ✅ Menu Dismissal
- **Escape** closes all context menus
- **Left click** anywhere dismisses menus
- **Scroll** dismisses menus
- **Right-click on background** dismisses menus (doesn't open new menu)

### ✅ Selection Management
- Selecting a new node **clears** previous subtree highlight
- Selecting a new edge **clears** previous edge highlight
- **Only one** node or edge selected at a time
- **Escape** clears all selections

### ✅ Global Event Handlers
- Listeners bound **once** (no duplicates on re-render)
- Unified `globalEscapeHandler` for all Escape scenarios
- Centralized `dismissAllMenus()` function
- Consistent `clearSelectionHighlights()` before new selections

## Test Files Structure

```
tests/
├── backend/                                    # Python backend tests (99 tests)
│   ├── conftest.py                            # Pytest fixtures and DB setup (13 fixtures)
│   ├── README.md                              # Backend testing guide
│   ├── unit/                                  # 73 unit tests
│   │   ├── test_crud.py                       # CRUD operations (23 tests, 100% passing)
│   │   ├── test_models.py                     # Model validation (27 tests, 100% passing)
│   │   └── test_schemas.py                    # Pydantic schemas (23 tests, 100% passing)
│   ├── integration/                           # 26 integration tests
│   │   └── test_import_workflow.py            # Full import pipeline (26 tests, 100% passing)
│   └── api/                                   # 41 API tests (pending fix)
│       ├── test_people_routes.py              # /people endpoints (24 tests)
│       └── test_relationships_routes.py       # /relationships endpoints (17 tests)
│
├── frontend/                                  # JavaScript frontend tests (86+ tests)
│   ├── README.md                              # Frontend testing guide
│   ├── unit/
│   │   ├── context-menu.test.js              # Menu functions
│   │   ├── import-export.test.js             # Import/export validation
│   │   └── importer-formats.test.js          # Format handling
│   └── e2e/
│       ├── ui-interactions.spec.js           # UI interaction tests
│       ├── bug-fixes.spec.js                 # Regression tests
│       └── import-export.spec.js             # Import/export workflows
│
├── fixtures/
│   └── sample-trees.json                      # Test data fixtures
│
├── setup.js                                   # Jest configuration
├── teardown.js                                # Test cleanup
├── README.md                                  # Testing guide
├── MANUAL_TEST_CHECKLIST.md                   # Manual testing guide
├── TEST_SUITE_SUMMARY.md                      # Detailed documentation
└── run-all-tests.sh                           # Run all tests script
```

## Test Commands

```bash
# Backend tests (Python)
pytest tests/backend/ -v                       # Run all backend tests (140 total, 99 passing)
pytest tests/backend/unit/ -v                  # Run unit tests only (73 tests)
pytest tests/backend/integration/ -v           # Run integration tests (26 tests)
pytest tests/backend/unit/test_crud.py -v      # Run specific test file
pytest tests/backend/ --cov=app                # Run with coverage report (26% overall)
pytest tests/backend/unit/ -v                  # Unit tests only
pytest tests/backend/integration/ -v           # Integration tests only
pytest tests/backend/ --cov=app                # With coverage report
pytest tests/backend/ --cov=app --cov-report=html  # HTML coverage

# Frontend tests (JavaScript)
npm test                                       # Jest unit tests with coverage
npm run test:watch                             # Unit tests in watch mode
npm run test:coverage                          # Coverage report
npm run test:e2e                               # Playwright E2E tests
npm run test:e2e:ui                            # E2E tests with UI
npm run test:all                               # All tests (unit + e2e)
```

## Configuration

- **Jest Config**: `jest.config.js`
- **Playwright Config**: `playwright.config.js`  
- **Test Setup**: `tests/setup.js`

## Writing New Tests

### Unit Test Example
```javascript
// tests/unit/my-feature.test.js
describe('My Feature', () => {
  test('should do something', () => {
    // Test implementation
  });
});
```

### E2E Test Example
```javascript
// tests/e2e/my-feature.spec.js
const { test, expect } = require('@playwright/test');

test('should interact correctly', async ({ page }) => {
  await page.goto('/');
  // Test implementation
});
```

## CI/CD Integration

The test suite is CI-ready:
- Automatic server startup via `playwright.config.js` webServer
- Retry logic for flaky tests
- Screenshots on failure
- Trace recording for debugging

Example CI configuration:
```yaml
- name: Install dependencies
  run: npm install && npx playwright install --with-deps

- name: Run tests
  run: npm run test:e2e
```

## Manual Testing

Before committing changes, verify using the manual checklist:
```bash
cat tests/MANUAL_TEST_CHECKLIST.md
```

## Debugging

### View test results
```bash
npx playwright show-report
```

### Run specific test
```bash
npx playwright test bug-fixes.spec.js
```

### Debug mode
```bash
npx playwright test --debug
```

### View Jest coverage
```bash
npm test -- --coverage
```

## Troubleshooting

**Tests fail to start server:**
- Ensure backend dependencies are installed: `poetry install`
- Check port 8888 is available: `lsof -i :8888`

**Playwright browser not found:**
```bash
npx playwright install chromium
```

**Tests timeout:**
- Increase timeout in `playwright.config.js`
- Check network/backend performance

## Documentation

- [Test Suite Summary](tests/TEST_SUITE_SUMMARY.md) - Comprehensive test documentation
- [Manual Test Checklist](tests/MANUAL_TEST_CHECKLIST.md) - Step-by-step manual testing
- [Playwright Docs](https://playwright.dev) - E2E testing reference
- [Jest Docs](https://jestjs.io) - Unit testing reference
