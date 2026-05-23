const fs = require('fs');
const path = require('path');

/** Cloudinary free tier raw file limit (10 MB). */
const DEFAULT_MAX_BYTES = 10 * 1024 * 1024;

function glbEmbeddedImageCount(abs) {
  try {
    const buf = fs.readFileSync(abs);
    if (buf.length < 20) return 0;
    const jsonLen = buf.readUInt32LE(12);
    const json = JSON.parse(buf.slice(20, 20 + jsonLen).toString('utf8'));
    return (json.images || []).length;
  } catch {
    return 0;
  }
}

function isGrarahPath(rel) {
  return /(^|\/)3d grarah\//i.test(rel);
}

/**
 * Decide which GLBs to upload.
 * Grarah: upload textured `optimized/` (~2MB); skip texture-less Tripo `mobile/`.
 * Other dresses: skip `original/` (30MB+) and oversized files.
 */
function filterGlbsForUpload(allFiles, modelRootPath, options = {}) {
  const maxBytes = options.maxBytes ?? DEFAULT_MAX_BYTES;
  const skipOriginal = options.skipOriginal !== false;
  const skipOptimizedIfMobile =
    options.skipOptimizedIfMobile !== false;

  const mobilePaths = new Set();
  for (const abs of allFiles) {
    const rel = path.relative(modelRootPath, abs).replace(/\\/g, '/');
    if (rel.includes('/mobile/')) {
      const key = rel.replace(/\/mobile\//, '::');
      mobilePaths.add(key);
    }
  }

  const toUpload = [];
  const skipped = [];

  for (const abs of allFiles) {
    const rel = path.relative(modelRootPath, abs).replace(/\\/g, '/');
    const stat = fs.statSync(abs);
    const size = stat.size;
    const grarah = isGrarahPath(rel);
    const images = glbEmbeddedImageCount(abs);

    if (skipOriginal && rel.includes('/original/')) {
      skipped.push({
        relativePath: `3d model/${rel}`,
        filePath: abs,
        reason: grarah
          ? 'original folder skipped (30MB+; app uses optimized/ with textures)'
          : 'original folder skipped (30MB+ files; app uses mobile/)',
        bytes: size,
      });
      continue;
    }

    if (grarah && rel.includes('/mobile/') && images === 0) {
      skipped.push({
        relativePath: `3d model/${rel}`,
        filePath: abs,
        reason: 'grarah mobile skipped (texture-less Tripo; app uses optimized/)',
        bytes: size,
      });
      continue;
    }

    if (
      skipOptimizedIfMobile &&
      !grarah &&
      rel.includes('/optimized/') &&
      mobilePaths.has(rel.replace(/\/optimized\//, '::'))
    ) {
      skipped.push({
        relativePath: `3d model/${rel}`,
        filePath: abs,
        reason: 'optimized skipped (mobile/ version will be uploaded)',
        bytes: size,
      });
      continue;
    }

    if (size > maxBytes) {
      const mobileAbs = mobileCounterpartPath(abs, modelRootPath);
      skipped.push({
        relativePath: `3d model/${rel}`,
        filePath: abs,
        reason: mobileAbs
          ? `file too large for Cloudinary (${formatMb(size)}); use mobile/ copy`
          : `file too large for Cloudinary (${formatMb(size)} > ${formatMb(maxBytes)})`,
        bytes: size,
      });
      continue;
    }

    toUpload.push(abs);
  }

  return { toUpload, skipped };
}

function mobileCounterpartPath(fileAbs, modelRoot) {
  const rel = path.relative(modelRoot, fileAbs).replace(/\\/g, '/');
  const parts = rel.split('/');
  const fileName = parts.pop();
  const dir = parts.join('/');
  const candidate = path.join(modelRoot, dir, 'mobile', fileName);
  return fs.existsSync(candidate) ? candidate : null;
}

function formatMb(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

/** Grarah optimized → legacy mobile kebab catalog alias. */
function grarahMobileAliasFromOptimized(relativePath) {
  const m = relativePath.match(
    /^3d model\/3d grarah\/(shirt|peplum)\/optimized\/optimized-(.+)\.(glb)$/i,
  );
  if (!m) return null;
  return `3d model/3d grarah/${m[1]}/mobile/${m[2]}.${m[3]}`;
}

/** Extra catalog rows so resolver paths resolve. */
function catalogAliasesFromUpload(meta, url) {
  const rows = [
    {
      name: meta.name,
      url,
      folder: meta.folder,
      category: meta.category,
      relativePath: meta.relativePath,
      subcategory: meta.subcategory,
    },
  ];

  if (meta.relativePath.includes('/mobile/')) {
    rows.push({
      name: meta.name,
      url,
      folder: meta.folder,
      category: meta.category,
      relativePath: meta.relativePath.replace('/mobile/', '/'),
      subcategory: meta.subcategory,
      aliasOf: meta.relativePath,
    });
  }

  const grarahMobile = grarahMobileAliasFromOptimized(meta.relativePath);
  if (grarahMobile) {
    rows.push({
      name: meta.name,
      url,
      folder: meta.folder,
      category: meta.category,
      relativePath: grarahMobile,
      subcategory: meta.subcategory,
      aliasOf: meta.relativePath,
    });
  }

  return rows;
}

module.exports = {
  filterGlbsForUpload,
  catalogAliasesFromUpload,
  glbEmbeddedImageCount,
  DEFAULT_MAX_BYTES,
};
