const path = require('path');

/** Safe Cloudinary folder segment (no spaces/special chars). */
function sanitizeSegment(segment) {
  return String(segment || 'root')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9._-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '') || 'root';
}

/**
 * Derive category / subcategory / Cloudinary folder from a file under MODEL_ROOT.
 * Example: `3d long frock/mobile/foo.glb` → category `3d-long-frock`, subcategory `mobile`.
 */
function metadataFromAbsolute(fileAbsolute, modelRootPath, cloudinaryBaseFolder) {
  const rel = path.relative(modelRootPath, fileAbsolute).replace(/\\/g, '/');
  const segments = rel.split('/').filter(Boolean);
  const fileName = segments[segments.length - 1] || 'model.glb';
  const dirParts = segments.slice(0, -1);

  const categoryRaw = dirParts[0] || 'uncategorized';
  const subcategoryRaw = dirParts.length > 1 ? dirParts.slice(1).join('/') : 'root';

  const category = sanitizeSegment(categoryRaw);
  const subcategory = sanitizeSegment(subcategoryRaw.replace(/\//g, '-'));

  const baseName = fileName.replace(/\.glb$/i, '');
  const publicId = sanitizeSegment(baseName);

  const folder = `${cloudinaryBaseFolder}/${category}/${subcategory}`;
  /** Frontend resolver paths always start with `3d model/`. */
  const relativePath = `3d model/${rel}`;

  return {
    name: fileName,
    category: categoryRaw,
    subcategory: subcategoryRaw,
    folder,
    relativePath,
    publicId,
    localRelative: rel,
  };
}

/** Normalize for Map lookup (case-insensitive, forward slashes). */
function normalizeRelativePath(p) {
  return String(p || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .trim()
    .toLowerCase();
}

module.exports = { sanitizeSegment, metadataFromAbsolute, normalizeRelativePath };
