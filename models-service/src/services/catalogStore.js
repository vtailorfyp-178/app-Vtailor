const fs = require('fs');
const path = require('path');
const DressGlbModel = require('../models/DressGlbModel');
const { RESULTS_DIR, SKIP_MONGODB } = require('../config/env');

const RESULTS_FILE = path.join(RESULTS_DIR, 'uploadResults.json');

function mapRow(row) {
  return {
    name: row.name,
    url: row.url,
    folder: row.folder,
    category: row.category,
    relativePath: row.relativePath,
    subcategory: row.subcategory,
  };
}

function readJsonCatalog() {
  if (!fs.existsSync(RESULTS_FILE)) return [];
  try {
    const raw = JSON.parse(fs.readFileSync(RESULTS_FILE, 'utf8'));
    return Array.isArray(raw) ? raw.map(mapRow).filter((r) => r.url) : [];
  } catch {
    return [];
  }
}

/** MongoDB first; fallback to uploadResults.json (works without Atlas). */
async function listAllModels() {
  if (!SKIP_MONGODB) {
    try {
      const count = await DressGlbModel.estimatedDocumentCount();
      if (count > 0) {
        const docs = await DressGlbModel.find({})
          .select('name category folder cloudinaryUrl relativePath subcategory')
          .sort({ category: 1, name: 1 })
          .lean();
        return docs.map((d) => ({
          name: d.name,
          url: d.cloudinaryUrl,
          folder: d.folder,
          category: d.category,
          relativePath: d.relativePath,
          subcategory: d.subcategory,
        }));
      }
    } catch (err) {
      console.warn('[catalog] MongoDB read failed, using JSON file:', err.message);
    }
  }

  return readJsonCatalog();
}

async function findByRelativePath(pathQuery) {
  const all = await listAllModels();
  const key = String(pathQuery || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .trim()
    .toLowerCase();
  return all.find((m) => m.relativePath && m.relativePath.toLowerCase() === key) || null;
}

module.exports = { listAllModels, findByRelativePath, readJsonCatalog };
