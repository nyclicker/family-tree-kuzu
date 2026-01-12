# Family Tree Frontend - Automated Testing

## Quick Start

```bash
# 1. Install dependencies
npm install
npx playwright install chromium

# 2. Start the backend server (in separate terminal)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8888

# 3. Run tests
npm test                    # Unit tests only
npm run test:e2e           # E2E tests only  
./tests/run-all-tests.sh   # All tests
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

## Test Files

```
tests/
├── unit/
│   └── context-menu.test.js      # Unit tests for JS functions
├── e2e/
│   ├── ui-interactions.spec.js   # Comprehensive E2E tests
│   └── bug-fixes.spec.js         # Targeted bug fix validation
├── setup.js                       # Jest/mock configuration
├── README.md                      # This file
├── TEST_SUITE_SUMMARY.md         # Detailed test documentation
├── MANUAL_TEST_CHECKLIST.md      # Manual testing guide
├── run-all-tests.sh              # Run all tests script
└── validate-setup.sh             # Verify test setup
```

## Test Commands

```bash
npm test                 # Run Jest unit tests
npm run test:watch       # Unit tests in watch mode
npm run test:e2e         # Run Playwright E2E tests
npm run test:e2e:ui      # E2E tests with UI (interactive)
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
