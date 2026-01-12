# Family Tree Frontend Tests

This directory contains automated tests for the family tree web application.

## Test Structure

- `unit/` - Unit tests for individual JavaScript functions
- `e2e/` - End-to-end tests using Playwright

## Running Tests

### Install Dependencies

```bash
npm install
npx playwright install
```

### Run Unit Tests

```bash
npm test
```

### Run E2E Tests

```bash
# Run all e2e tests
npm run test:e2e

# Run with UI mode (interactive)
npm run test:e2e:ui
```

## Test Coverage

### Unit Tests
- Context menu display/hide logic
- Selection and highlighting
- Global event handlers (Escape, click, scroll)
- Parent pick mode
- Edge/node detection
- Subtree highlighting

### E2E Tests
- Context menu interactions
  - Escape closes menus
  - Click dismisses menus
  - Right-click background closes menus
  - Scroll dismisses menus
- Node selection
  - Clicking highlights subtree
  - Second click clears first selection
  - Escape clears selection
- Edge selection
  - Clicking highlights edge
  - Right-click shows delete menu
  - Second click clears first selection
- Parent pick mode
  - Escape cancels mode
  - Background right-click cancels
- Tree management
  - Draft counting
  - Graph rendering

## Known Issues to Test

Based on recent changes, these tests verify:

1. **Menu Dismissal**: All context menus close on Escape, click, scroll, or background right-click
2. **Single Selection**: Only one node/edge is selected at a time; new selections clear old ones
3. **Global Escape**: Escape key works consistently to exit all modes and clear selections
4. **Parent Pick Cancellation**: Right-click on background exits parent pick mode properly

## Test Configuration

- **Jest** for unit tests with jsdom environment
- **Playwright** for E2E tests with Chromium
- Automatic server startup for E2E tests via webServer config
