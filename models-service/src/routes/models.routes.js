const express = require('express');
const { listAllModels, findByRelativePath } = require('../services/catalogStore');

const router = express.Router();

/**
 * GET /models
 * Catalog for Expo app (Cloudinary URLs).
 */
router.get('/', async (_req, res, next) => {
  try {
    const payload = await listAllModels();
    res.set('Cache-Control', 'public, max-age=300');
    res.json(payload);
  } catch (err) {
    next(err);
  }
});

/**
 * GET /models/by-path?path=3d%20model%2F...
 */
router.get('/by-path', async (req, res, next) => {
  try {
    const raw = String(req.query.path || '').trim();
    if (!raw) {
      return res.status(400).json({ detail: 'Query param "path" is required' });
    }

    const doc = await findByRelativePath(raw);
    if (!doc) {
      return res.status(404).json({ detail: 'Model not found for path', path: raw });
    }

    return res.json({
      name: doc.name,
      url: doc.url,
      folder: doc.folder,
      category: doc.category,
      relativePath: doc.relativePath,
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
