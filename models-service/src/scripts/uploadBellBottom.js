/**
 * Upload all bell-bottom optimized GLBs + MongoDB metadata.
 * Prerequisites:
 *   1. Place source GLBs in `3d model/3d trouser shirt/bell-bottom/original/`
 *   2. Run: cd app-vTailor-frontend/app-vTailor && npm run compress:bell-bottom
 *   3. Run: npm run upload:bell-bottom
 *   4. cd app-vTailor-frontend/app-vTailor && node scripts/sync-cloudinary-catalog.mjs
 */

const fs = require('fs');
const path = require('path');
const { connectDatabase, disconnectDatabase } = require('../config/database');
const { cloudinary, uploadGlbRaw } = require('../config/cloudinary');
const {
  CLOUDINARY_CLOUD_NAME,
  MODEL_ROOT_PATH,
  CLOUDINARY_BASE_FOLDER,
  SKIP_MONGODB,
} = require('../config/env');
const DressGlbModel = require('../models/DressGlbModel');
const { metadataFromAbsolute, normalizeRelativePath } = require('../utils/pathMetadata');
const { catalogAliasesFromUpload } = require('../utils/filterGlbsForUpload');
const {
  listBellBottomVariants,
  GLB_FILENAME_BY_NECK_SLEEVE,
} = require('../config/bellBottomCatalog');

const OPT_DIR = path.join(MODEL_ROOT_PATH, '3d trouser shirt', 'bell-bottom', 'optimized');

async function uploadOne(filePath, variantMeta) {
  const bytes = fs.statSync(filePath).size;
  if (bytes > 10 * 1024 * 1024) {
    throw new Error(`${path.basename(filePath)} is ${(bytes / 1e6).toFixed(2)} MB (max 10 MB)`);
  }

  const meta = metadataFromAbsolute(filePath, MODEL_ROOT_PATH, CLOUDINARY_BASE_FOLDER);
  const result = await uploadGlbRaw(filePath, meta.folder, meta.publicId);
  const url = result.secure_url || result.url;

  if (!SKIP_MONGODB) {
    await DressGlbModel.findOneAndUpdate(
      { relativePath: meta.relativePath },
      {
        name: meta.name,
        category: variantMeta.category,
        subcategory: variantMeta.subCategory,
        folder: meta.folder,
        relativePath: meta.relativePath,
        relativePathKey: normalizeRelativePath(meta.relativePath),
        cloudinaryUrl: url,
        publicId: result.public_id,
        bytes: result.bytes,
        uploadedAt: new Date(),
        variation: variantMeta.variation,
        neckType: variantMeta.neckType,
        sleeveType: variantMeta.sleeveType,
        previewImage: variantMeta.previewImage,
        thumbnail: variantMeta.thumbnail,
        colors: variantMeta.colors,
      },
      { upsert: true, new: true },
    );
  }

  const row = { relativePath: meta.relativePath, url, aliasOf: null };
  return [row, ...catalogAliasesFromUpload(row)];
}

async function main() {
  if (!fs.existsSync(OPT_DIR)) {
    console.error('Missing optimized folder:', OPT_DIR);
    console.error('Run compress:bell-bottom first.');
    process.exit(1);
  }

  console.log('Cloudinary:', CLOUDINARY_CLOUD_NAME);
  await cloudinary.api.ping();
  if (!SKIP_MONGODB) await connectDatabase();

  const variants = listBellBottomVariants();
  const catalogRows = [];
  let uploaded = 0;
  let skipped = 0;

  for (const variant of variants) {
    const fileName = GLB_FILENAME_BY_NECK_SLEEVE[variant.neckType][variant.sleeveType];
    const filePath = path.join(OPT_DIR, fileName);
    if (!fs.existsSync(filePath)) {
      console.warn('Skip (missing):', fileName);
      skipped += 1;
      continue;
    }
    console.log('Uploading', fileName, `(${(fs.statSync(filePath).size / 1e6).toFixed(2)} MB)`);
    const rows = await uploadOne(filePath, variant);
    catalogRows.push(...rows);
    uploaded += 1;
  }

  const outDir = path.join(__dirname, '../../data');
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, 'uploadBellBottomResults.json');
  fs.writeFileSync(outFile, JSON.stringify(catalogRows, null, 2));

  console.log(`Done: ${uploaded} uploaded, ${skipped} skipped. Wrote ${outFile}`);
  if (!SKIP_MONGODB) await disconnectDatabase();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
