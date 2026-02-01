module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['**/tests/frontend/unit/**/*.test.js'],
  collectCoverageFrom: [
    'web/**/*.js',
    '!web/**/*.test.js',
    '!web/index.html',
  ],
  coverageReporters: ['text', 'lcov', 'html'],
  coveragePathIgnorePatterns: ['/node_modules/'],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],
};
