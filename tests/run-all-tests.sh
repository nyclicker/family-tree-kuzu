#!/bin/bash

# Quick test runner script

set -e

echo "========================================"
echo "Running Family Tree Frontend Tests"
echo "========================================"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
    npx playwright install
fi

echo ""
echo "1. Running Unit Tests..."
echo "----------------------------------------"
npm test -- --passWithNoTests

echo ""
echo "2. Running E2E Tests..."
echo "----------------------------------------"
npm run test:e2e

echo ""
echo "========================================"
echo "All tests completed!"
echo "========================================"
