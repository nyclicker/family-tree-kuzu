# Frontend Testing Guide

This guide covers testing the JavaScript frontend using Jest (unit tests) and Playwright (E2E tests).

## Setup

### Install Dependencies

```bash
# Install frontend dependencies
npm install

# Install Playwright browsers
npx playwright install chromium
```

## Running Tests

### Run All Frontend Tests
```bash
npm run test:all    # Unit + E2E tests
```

### Run Unit Tests (Jest)
```bash
npm test                        # Run all unit tests with coverage
npm run test:watch              # Watch mode for development
npm run test:coverage           # Generate coverage report
```

### Run E2E Tests (Playwright)
```bash
npm run test:e2e                # Run all E2E tests
npm run test:e2e:ui             # Interactive UI mode (recommended for development)
```

## Test Structure

### Unit Tests (`tests/frontend/unit/`)

**context-menu.test.js** - Context menu functions
- Menu display/hide logic (currently placeholder - needs implementation)
- Selection clearing
- Event handlers

**import-export.test.js** - Import/export validation
- Export data structure validation (5 tests)
- Filename generation logic (5 tests)
- Version management (5 tests)
- Data validation (5 tests)
- Import payload structure (4 tests)

**importer-formats.test.js** - Format handling
- Text/CSV format detection (4 tests)
- CSV parsing and compatibility (5 tests)
- JSON format validation (10+ tests)
- Person/relationship record fields

### E2E Tests (`tests/frontend/e2e/`)

**ui-interactions.spec.js** - Comprehensive UI tests (~380 lines)
- Context menu behavior (Escape, click, scroll, right-click dismissal)
- Node selection and highlighting
- Edge selection and highlighting
- Parent pick mode workflows
- Tree and draft management
- Graph rendering

**bug-fixes.spec.js** - Regression tests (~200 lines)
- Menu dismissal fixes (12 tests)
- Selection clearing
- Listener binding

**import-export.spec.js** - Import/export workflows (~335 lines)
- Export endpoint JSON structure
- Tree metadata inclusion
- File download behavior
- Save-to-disk functionality
- Version history cleanup

## Test Fixtures

Shared test data is in `tests/fixtures/`:
- **sample-trees.json**: Sample family tree data with various structures

## Writing New Tests

### Example: Unit Test

```javascript
describe('Context Menu Functions', () => {
  test('dismissAllMenus removes all menu elements', () => {
    // Setup
    document.body.innerHTML = '<div id="ctxMenu" style="display: block;"></div>';
    
    // Execute
    dismissAllMenus();
    
    // Verify
    const menu = document.getElementById('ctxMenu');
    expect(menu.style.display).toBe('none');
  });
});
```

### Example: E2E Test

```javascript
test('Escape key should close context menus', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('#graph');
  
  // Right-click to open menu
  const graph = page.locator('#graph');
  await graph.click({ button: 'right' });
  
  // Verify menu is visible
  const menu = page.locator('#ctxMenu');
  await expect(menu).toBeVisible();
  
  // Press Escape
  await page.keyboard.press('Escape');
  
  // Verify menu is hidden
  await expect(menu).not.toBeVisible();
});
```

## Configuration Files

- **jest.config.js**: Unit test configuration, coverage thresholds
- **playwright.config.js**: E2E test configuration, browser settings
- **tests/setup.js**: Jest setup (mock DOM, global config)
- **tests/teardown.js**: Cleanup after test runs

## Coverage Reports

### Generate Coverage
```bash
npm test                              # Generates coverage/
npm run test:coverage                 # Coverage + report message
```

### View Coverage
```bash
open coverage/lcov-report/index.html  # Open HTML report
```

### Coverage Thresholds
Current targets (configured in jest.config.js):
- Branches: 50%
- Functions: 50%
- Lines: 50%
- Statements: 50%

## CI/CD Integration

Tests run automatically via GitHub Actions:

**Frontend Tests** (`.github/workflows/frontend-tests.yml`):
- Runs on: Node.js 18
- Includes: Jest unit tests + Playwright E2E
- Triggers: Push to main/develop, pull requests
- Coverage: Uploaded to Codecov

## Common Issues

### "Module not found" in Jest
- Ensure you're in workspace root: `cd /workspaces/family-tree`
- Install dependencies: `npm install`

### Playwright browser not found
- Install browsers: `npx playwright install chromium`

### E2E tests timing out
- Increase timeout in playwright.config.js: `timeout: 60000`
- Check that backend server is running on port 8080

### Tests fail in watch mode
- Clear Jest cache: `npx jest --clearCache`
- Restart watch mode: `npm run test:watch`

## Test Organization

```
tests/frontend/
├── unit/                           # Jest unit tests
│   ├── context-menu.test.js       # UI component tests
│   ├── import-export.test.js      # Import/export logic
│   └── importer-formats.test.js   # Format validation
│
├── e2e/                            # Playwright E2E tests
│   ├── ui-interactions.spec.js    # User interactions
│   ├── bug-fixes.spec.js          # Regression tests
│   └── import-export.spec.js      # Workflow tests
│
└── README.md                       # This file
```

## Best Practices

1. **Unit Tests**: Test pure functions, data transformations, validation logic
2. **E2E Tests**: Test user workflows, UI interactions, integration scenarios
3. **Fixtures**: Use shared test data from `tests/fixtures/`
4. **Isolation**: Each test should be independent and clean up after itself
5. **Descriptive Names**: Test names should describe what's being tested
6. **Async/Await**: Always await promises in E2E tests

## Next Steps

**Immediate Priorities**:
- [ ] Replace placeholder tests in context-menu.test.js with real implementations
- [ ] Refactor web/app.js to extract testable functions
- [ ] Add error scenario tests
- [ ] Add accessibility tests

**Phase 3 Goals**:
- [ ] 60%+ unit test coverage
- [ ] Cross-browser E2E tests (Firefox, Safari)
- [ ] Visual regression tests
- [ ] Performance tests

See [TEST_COVERAGE_ASSESSMENT.md](../TEST_COVERAGE_ASSESSMENT.md) for detailed roadmap.
