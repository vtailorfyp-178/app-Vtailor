const express = require('express');
const DressGlbModel = require('../models/DressGlbModel');
const { findByRelativePath } = require('../services/catalogStore');
const {
  CATEGORY,
  SUB_CATEGORY,
  VARIATION,
  NECK_TYPES,
  SLEEVE_TYPES,
  relativePathForNeckSleeve,
  listBellBottomVariants,
} = require('../config/bellBottomCatalog');
const { normalizeRelativePath } = require('../utils/pathMetadata');

const router = express.Router();

const CASUAL_CATEGORIES = [
  { id: 'casual', name: 'Casual dress' },
];

const TROUSER_SHIRT_SUBCATEGORIES = [{ id: 'trouser-shirt', name: 'Trouser shirt' }];

const BELL_BOTTOM_VARIATIONS = [
  {
    id: 'bell-bottom',
    name: 'Bell bottom',
    thumbnail: null,
    previewImage: null,
  },
];

/** Fabric shade ids (same families as app `CASUAL_FABRIC_COLOR_FAMILIES`). */
const BELL_BOTTOM_COLOR_SHADE_IDS = [
  'red-classic',
  'pink-rani',
  'blue-royal',
  'green-mint',
  'purple-lavender',
  'orange-tangerine',
  'teal-classic',
  'black-jet',
  'white-pure',
];

async function findModelDoc(relativePath) {
  const key = normalizeRelativePath(relativePath);
  const fromJson = await findByRelativePath(relativePath);
  if (fromJson?.url) {
    return {
      relativePath,
      modelUrl: fromJson.url,
      cloudinaryUrl: fromJson.url,
    };
  }
  const doc = await DressGlbModel.findOne({ relativePathKey: key }).lean();
  if (!doc) return null;
  return {
    relativePath: doc.relativePath,
    modelUrl: doc.cloudinaryUrl,
    cloudinaryUrl: doc.cloudinaryUrl,
    previewImage: doc.previewImage || null,
    thumbnail: doc.thumbnail || null,
    colors: doc.colors || [],
  };
}

router.get('/categories', (_req, res) => {
  res.set('Cache-Control', 'public, max-age=600');
  res.json({ categories: CASUAL_CATEGORIES });
});

router.get('/variations', (_req, res) => {
  res.set('Cache-Control', 'public, max-age=600');
  res.json({
    category: CATEGORY,
    subCategory: SUB_CATEGORY,
    variations: BELL_BOTTOM_VARIATIONS,
  });
});

router.get('/neck-types', (_req, res) => {
  res.set('Cache-Control', 'public, max-age=600');
  res.json({ neckTypes: NECK_TYPES });
});

router.get('/sleeve-types', (_req, res) => {
  res.set('Cache-Control', 'public, max-age=600');
  res.json({ sleeveTypes: SLEEVE_TYPES });
});

router.get('/colors', (_req, res) => {
  res.set('Cache-Control', 'public, max-age=600');
  res.json({
    /** Client applies hex via `dressFabricColors`; these are stable shade ids. */
    colorShadeIds: BELL_BOTTOM_COLOR_SHADE_IDS,
    runtimeTint: true,
  });
});

router.get('/subcategories', (_req, res) => {
  res.set('Cache-Control', 'public, max-age=600');
  res.json({ subCategories: TROUSER_SHIRT_SUBCATEGORIES });
});

/** Full matrix with optional Cloudinary URLs when uploaded. */
router.get('/catalog', async (_req, res, next) => {
  try {
    const variants = listBellBottomVariants();
    const enriched = await Promise.all(
      variants.map(async (row) => {
        const doc = row.relativePath ? await findModelDoc(row.relativePath) : null;
        return {
          ...row,
          modelUrl: doc?.modelUrl ?? null,
        };
      }),
    );
    res.set('Cache-Control', 'public, max-age=120');
    res.json({ variation: VARIATION, variants: enriched });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /bell-bottom/model?neck=round&sleeve=straight
 */
router.get('/model', async (req, res, next) => {
  try {
    const neck = String(req.query.neck || '').trim();
    const sleeve = String(req.query.sleeve || '').trim();
    if (!neck || !sleeve) {
      return res.status(400).json({ detail: 'Query params "neck" and "sleeve" are required' });
    }

    const relativePath = relativePathForNeckSleeve(neck, sleeve);
    if (!relativePath) {
      return res.status(400).json({ detail: 'Invalid neck or sleeve id', neck, sleeve });
    }

    const doc = await findModelDoc(relativePath);
    if (!doc?.modelUrl) {
      return res.status(404).json({
        detail: 'GLB not uploaded yet for this combination',
        relativePath,
        neck,
        sleeve,
      });
    }

    return res.json({
      category: CATEGORY,
      subCategory: SUB_CATEGORY,
      variation: VARIATION,
      neckType: neck,
      sleeveType: sleeve,
      relativePath,
      modelUrl: doc.modelUrl,
      previewImage: doc.previewImage,
      thumbnail: doc.thumbnail,
      colors: doc.colors,
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
