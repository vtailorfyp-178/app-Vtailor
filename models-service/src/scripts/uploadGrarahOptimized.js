/**
 * Upload only grarah shirt/peplum optimized/ GLBs (textured, <10MB).
 * Run: npm run upload:grarah-optimized
 * Then: cd app-vTailor-frontend/app-vTailor && node scripts/sync-cloudinary-catalog.mjs
 */

const fs = require('fs');
const path = require('path');
const { connectDatabase, disconnectDatabase } = require('../config/database');
const { cloudinary, uploadGlbRaw } = require('../config/cloudinary');
const { CLOUDINARY_CLOUD_NAME } = require('../config/env');
const {
  MODEL_ROOT_PATH,
  CLOUDINARY_BASE_FOLDER,
  UPLOAD_DELAY_MS,
  UPLOAD_MAX_RETRIES,
  RESULTS_DIR,
  SKIP_MONGODB,
} = require('../config/env');
const DressGlbModel = require('../models/DressGlbModel');
const { scanGlbFiles } = require('../utils/scanGlbs');
const { metadataFromAbsolute } = require('../utils/pathMetadata');
const {
  filterGlbsForUpload,
  catalogAliasesFromUpload,
  glbEmbeddedImageCount,
} = require('../utils/filterGlbsForUpload');

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function uploadWithRetry(filePath, folder, publicId) {
  let lastError;
  for (let attempt = 0; attempt <= UPLOAD_MAX_RETRIES; attempt++) {
    try {
      return await uploadGlbRaw(filePath, folder, publicId);
    } catch (err) {
      lastError = err;
      if (attempt < UPLOAD_MAX_RETRIES) await sleep(UPLOAD_DELAY_MS);
    }
  }
  throw lastError;
}

async function upsertModel(meta, cloudinaryResult) {
  const url = cloudinaryResult.secure_url || cloudinaryResult.url;
  if (SKIP_MONGODB) return url;

  await DressGlbModel.findOneAndUpdate(
    { relativePath: meta.relativePath },
    {
      name: meta.name,
      category: meta.category,
      subcategory: meta.subcategory,
      folder: meta.folder,
      relativePath: meta.relativePath,
      cloudinaryUrl: url,
      publicId: cloudinaryResult.public_id,
      bytes: cloudinaryResult.bytes,
      uploadedAt: new Date(),
    },
    { upsert: true, new: true },
  );
  return url;
}

async function main() {
  console.log('Cloudinary cloud_name:', CLOUDINARY_CLOUD_NAME);
  await cloudinary.api.ping();
  console.log('Cloudinary OK\n');

  const allFiles = scanGlbFiles(MODEL_ROOT_PATH).filter((abs) => {
    const rel = path.relative(MODEL_ROOT_PATH, abs).replace(/\\/g, '/');
    return (
      rel.includes('3d grarah/') &&
      rel.includes('/optimized/') &&
      rel.endsWith('.glb') &&
      !rel.includes('optimized-optimized')
    );
  });

  const textured = allFiles.filter((abs) => glbEmbeddedImageCount(abs) > 0);
  console.log(`Grarah optimized on disk: ${allFiles.length}, with textures: ${textured.length}\n`);

  const { toUpload, skipped } = filterGlbsForUpload(textured, MODEL_ROOT_PATH, {
    skipOptimizedIfMobile: false,
  });

  console.log(`Will upload ${toUpload.length} textured grarah optimized GLBs\n`);
  await connectDatabase();

  const successes = [];
  const failures = [];
  let n = 0;

  for (const filePath of toUpload) {
    n += 1;
    const meta = metadataFromAbsolute(filePath, MODEL_ROOT_PATH, CLOUDINARY_BASE_FOLDER);
    process.stdout.write(`[${n}/${toUpload.length}] ${meta.relativePath} … `);
    try {
      const result = await uploadWithRetry(filePath, meta.folder, meta.publicId);
      const url = await upsertModel(meta, result);
      for (const row of catalogAliasesFromUpload(meta, url)) {
        successes.push(row);
      }
      console.log('ok');
    } catch (err) {
      failures.push({ relativePath: meta.relativePath, error: err.message || String(err) });
      console.log('FAILED', err.message || err);
    }
    if (n < toUpload.length) await sleep(UPLOAD_DELAY_MS);
  }

  fs.mkdirSync(RESULTS_DIR, { recursive: true });
  const outPath = path.join(RESULTS_DIR, 'uploadGrarahOptimizedResults.json');
  fs.writeFileSync(outPath, JSON.stringify(successes, null, 2), 'utf8');
  console.log(`\nWrote ${successes.length} catalog rows → ${outPath}`);
  console.log(`Failed: ${failures.length}`);

  await disconnectDatabase();
  process.exit(failures.length > 0 ? 1 : 0);
}

main().catch(async (err) => {
  console.error(err);
  await disconnectDatabase().catch(() => {});
  process.exit(1);
});
