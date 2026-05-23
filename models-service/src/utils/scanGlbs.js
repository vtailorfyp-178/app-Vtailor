const fs = require('fs');
const path = require('path');

/**
 * Recursively collect all .glb files under modelRootPath.
 * @param {string} modelRootPath
 * @returns {string[]} absolute paths
 */
function scanGlbFiles(modelRootPath) {
  const results = [];

  function walk(dir) {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.glb')) {
        results.push(full);
      }
    }
  }

  walk(modelRootPath);
  return results.sort();
}

module.exports = { scanGlbFiles };
