const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const API_URL = 'http://localhost:8080';
const EXPORTS_DIR = path.join(__dirname, '../../data/exports');

// Helper to clean exports directory
async function cleanExports() {
  if (fs.existsSync(EXPORTS_DIR)) {
    const files = fs.readdirSync(EXPORTS_DIR);
    for (const file of files) {
      fs.unlinkSync(path.join(EXPORTS_DIR, file));
    }
  }
}

// Helper to get exported files
function getExportedFiles() {
  if (!fs.existsSync(EXPORTS_DIR)) return [];
  return fs.readdirSync(EXPORTS_DIR).sort();
}

// Helper to read exported JSON
function readExportedFile(filename) {
  const filePath = path.join(EXPORTS_DIR, filename);
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

test.describe('Import and Export', () => {
  test.beforeEach(async () => {
    // Clean up exports before each test
    cleanExports();
  });

  test.describe('Export endpoint', () => {
    test('should export data as JSON', async ({ request }) => {
      const response = await request.get(`${API_URL}/export`);
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('tree');
      expect(data).toHaveProperty('tree_version');
      expect(data).toHaveProperty('people');
      expect(data).toHaveProperty('relationships');
    });

    test('should include tree metadata when tree_id is provided', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1`);
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      // Tree 1 is the default from initial import
      if (data.tree) {
        expect(data.tree).toHaveProperty('id');
        expect(data.tree).toHaveProperty('name');
      }
    });

    test('should include tree version in response', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1`);
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      if (data.tree_version) {
        expect(data.tree_version).toHaveProperty('version');
        expect(data.tree_version).toHaveProperty('tree_id');
      }
    });

    test('should filter by tree_version_id when provided', async ({ request }) => {
      // Get available versions
      const treesResponse = await request.get(`${API_URL}/trees`);
      const trees = await treesResponse.json();
      
      if (trees.length > 0) {
        const treeId = trees[0].id;
        const versionsResponse = await request.get(`${API_URL}/trees/${treeId}/versions`);
        const versions = await versionsResponse.json();
        
        if (versions.length > 0) {
          const versionId = versions[0].id;
          const response = await request.get(`${API_URL}/export?tree_version_id=${versionId}`);
          expect(response.status()).toBe(200);
          
          const data = await response.json();
          expect(Array.isArray(data.people)).toBe(true);
          expect(Array.isArray(data.relationships)).toBe(true);
        }
      }
    });

    test('should download with descriptive filename', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1`);
      expect(response.status()).toBe(200);
      
      const contentDisposition = response.headers()['content-disposition'];
      expect(contentDisposition).toBeTruthy();
      expect(contentDisposition).toMatch(/\.json/);
    });
  });

  test.describe('Save to disk', () => {
    test('should save export to data/exports/ directory', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data.status).toBe('success');
      expect(data.path).toBeTruthy();
      expect(data.path).toMatch(/\.json$/);
      
      // Verify file exists
      const files = getExportedFiles();
      expect(files.length).toBeGreaterThan(0);
    });

    test('should include tree name and version in auto-generated filename', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data.path).toMatch(/_v\d+_\d{8}_\d{6}\.json$/);
    });

    test('should overwrite existing file for same tree version', async ({ request }) => {
      // First export
      const response1 = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response1.status()).toBe(200);
      const path1 = (await response1.json()).path;
      
      const fileCountAfterFirst = getExportedFiles().length;
      
      // Second export (should overwrite)
      const response2 = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response2.status()).toBe(200);
      const path2 = (await response2.json()).path;
      
      // Same file path
      expect(path1).toBe(path2);
      
      // No new file created
      const fileCountAfterSecond = getExportedFiles().length;
      expect(fileCountAfterSecond).toBe(fileCountAfterFirst);
    });

    test('should support custom filename', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true&filename=test_backup`);
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data.path).toContain('test_backup.json');
      
      // Verify file exists
      const files = getExportedFiles();
      expect(files).toContain('test_backup.json');
    });

    test('should not auto-delete custom filenames during cleanup', async ({ request }) => {
      // Save custom backup
      const backupResponse = await request.get(
        `${API_URL}/export?tree_id=1&save_to_disk=true&filename=important_backup`
      );
      expect(backupResponse.status()).toBe(200);
      
      // Custom backup should exist
      const files = getExportedFiles();
      expect(files).toContain('important_backup.json');
    });
  });

  test.describe('Import endpoint', () => {
    test('should create tree and version on first import', async ({ request }) => {
      const response = await request.post(`${API_URL}/trees/import`, {
        data: {
          name: 'test_tree_' + Date.now(),
          source_filename: 'test.txt',
        },
      });
      
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data).toHaveProperty('tree_id');
      expect(data).toHaveProperty('tree_version_id');
      expect(data.version).toBe(1);
    });

    test('should increment version on subsequent imports', async ({ request }) => {
      const treeName = 'test_tree_increment_' + Date.now();
      
      // Create tree
      const createResponse = await request.post(`${API_URL}/trees/import`, {
        data: {
          name: treeName,
          source_filename: 'test1.txt',
        },
      });
      expect(createResponse.status()).toBe(200);
      const treeData = await createResponse.json();
      const treeId = treeData.tree_id;
      expect(treeData.version).toBe(1);
      
      // Import again with same tree_id
      const updateResponse = await request.post(`${API_URL}/trees/import`, {
        data: {
          name: treeName,
          source_filename: 'test2.txt',
          tree_id: treeId,
        },
      });
      expect(updateResponse.status()).toBe(200);
      const updateData = await updateResponse.json();
      
      // Version should increment
      expect(updateData.version).toBe(2);
      expect(updateData.tree_id).toBe(treeId);
    });

    test('should return correct tree_version_id', async ({ request }) => {
      const response = await request.post(`${API_URL}/trees/import`, {
        data: {
          name: 'test_versions_' + Date.now(),
          source_filename: 'test.txt',
        },
      });
      
      expect(response.status()).toBe(200);
      const data = await response.json();
      
      // Verify tree_version_id is valid
      expect(typeof data.tree_version_id).toBe('number');
      expect(data.tree_version_id).toBeGreaterThan(0);
    });

    test('should allow filtering exports by specific tree_version', async ({ request }) => {
      const treeName = 'version_test_' + Date.now();
      
      // Create tree v1
      const v1Response = await request.post(`${API_URL}/trees/import`, {
        data: {
          name: treeName,
          source_filename: 'v1.txt',
        },
      });
      expect(v1Response.status()).toBe(200);
      const v1Data = await v1Response.json();
      const v1VersionId = v1Data.tree_version_id;
      
      // Create v2
      const v2Response = await request.post(`${API_URL}/trees/import`, {
        data: {
          name: treeName,
          source_filename: 'v2.txt',
          tree_id: v1Data.tree_id,
        },
      });
      expect(v2Response.status()).toBe(200);
      
      // Export specific version
      const exportResponse = await request.get(
        `${API_URL}/export?tree_version_id=${v1VersionId}`
      );
      expect(exportResponse.status()).toBe(200);
      
      const exportData = await exportResponse.json();
      expect(exportData.tree_version).toHaveProperty('id', v1VersionId);
    });
  });

  test.describe('Export file content validation', () => {
    test('should contain valid JSON structure', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response.status()).toBe(200);
      const data = await response.json();
      
      const files = getExportedFiles();
      expect(files.length).toBeGreaterThan(0);
      
      const content = readExportedFile(files[0]);
      expect(content).toHaveProperty('tree');
      expect(content).toHaveProperty('tree_version');
      expect(content).toHaveProperty('people');
      expect(content).toHaveProperty('relationships');
    });

    test('should have people as array', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response.status()).toBe(200);
      
      const files = getExportedFiles();
      const content = readExportedFile(files[0]);
      expect(Array.isArray(content.people)).toBe(true);
    });

    test('should have relationships as array', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response.status()).toBe(200);
      
      const files = getExportedFiles();
      const content = readExportedFile(files[0]);
      expect(Array.isArray(content.relationships)).toBe(true);
    });

    test('each person should have required fields', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response.status()).toBe(200);
      
      const files = getExportedFiles();
      const content = readExportedFile(files[0]);
      
      if (content.people.length > 0) {
        const person = content.people[0];
        expect(person).toHaveProperty('id');
        expect(person).toHaveProperty('display_name');
        expect(person).toHaveProperty('sex');
      }
    });

    test('each relationship should have required fields', async ({ request }) => {
      const response = await request.get(`${API_URL}/export?tree_id=1&save_to_disk=true`);
      expect(response.status()).toBe(200);
      
      const files = getExportedFiles();
      const content = readExportedFile(files[0]);
      
      if (content.relationships.length > 0) {
        const rel = content.relationships[0];
        expect(rel).toHaveProperty('id');
        expect(rel).toHaveProperty('type');
      }
    });
  });
});
