#!/bin/bash

# Quick smoke test - just validate the test setup works

set -e

cd /workspaces/family-tree

echo "========================================"
echo "Family Tree Test Validation"
echo "========================================"
echo ""

echo "Checking test file structure..."
ls -la tests/
echo ""

echo "Checking unit test files..."
ls -la tests/unit/
echo ""

echo "Checking e2e test files..."
ls -la tests/e2e/
echo ""

echo "Validating package.json..."
if [ -f "package.json" ]; then
    echo "✓ package.json exists"
    grep -q "jest" package.json && echo "✓ Jest configured"
    grep -q "playwright" package.json && echo "✓ Playwright configured"
else
    echo "✗ package.json missing"
    exit 1
fi
echo ""

echo "Validating test configs..."
[ -f "jest.config.js" ] && echo "✓ jest.config.js exists" || echo "✗ jest.config.js missing"
[ -f "playwright.config.js" ] && echo "✓ playwright.config.js exists" || echo "✗ playwright.config.js missing"
echo ""

echo "Checking dependencies..."
if [ -d "node_modules" ]; then
    echo "✓ node_modules installed"
    [ -d "node_modules/jest" ] && echo "✓ Jest installed"
    [ -d "node_modules/@playwright" ] && echo "✓ Playwright installed"
else
    echo "⚠ node_modules not found - run 'npm install'"
fi
echo ""

echo "========================================"
echo "Test setup validation complete!"
echo ""
echo "To run tests:"
echo "  npm test              # Unit tests"
echo "  npm run test:e2e      # E2E tests"
echo "  ./tests/run-all-tests.sh  # All tests"
echo "========================================"
