/**
 * Upload single Bridal lehnga optimized GLB (mahroon round short sleeves).
 * Run: node src/scripts/uploadBridalMahroonShort.js
 * Then: cd app-vTailor-frontend/app-vTailor && node scripts/sync-cloudinary-catalog.mjs
 */

const fs = require('fs');
const path = require('path');
const { connectDatabase, disconnectDatabase } = require('../config/database');
const { cloudinary, uploadGlbRaw } = require('../config/cloudinary');
const { CLOUDINARY_CLOUD_NAME, MODEL_ROOT_PATH, CLOUDINARY_BASE_FOLDER, SKIP_MONGODB } =
  require('../config/env');
const DressGlbModel = require('../models/DressGlbModel');
const { metadataFromAbsolute } = require('../utils/pathMetadata');
const { catalogAliasesFromUpload } = require('../utils/filterGlbsForUpload');

const REL = '3d lehnga/Bridal lehnga/optimized/optimized-mahroon-round-neck-short-sleeves-.glb';

async function main() {
  const filePath = path.join(MODEL_ROOT_PATH, REL.replace(/\//g, path.sep));
  if (!fs.existsSync(filePath)) {
    console.error('Missing file:', filePath);
    process.exit(1);
  }

  const bytes = fs.statSync(filePath).size;
  if (bytes > 10 * 1024 * 1024) {
    console.error(`File too large for Cloudinary (${(bytes / 1e6).toFixed(2)} MB). Re-run compress.`);
    process.exit(1);
  }

  console.log('Cloudinary:', CLOUDINARY_CLOUD_NAME);
  await cloudinary.api.ping();
  if (!SKIP_MONGODB) {
    await connectDatabase();
  }

  const meta = metadataFromAbsolute(filePath, MODEL_ROOT_PATH, CLOUDINARY_BASE_FOLDER);
  console.log('Uploading', meta.relativePath, `(${(bytes / 1e6).toFixed(2)} MB)`);

  const result = await uploadGlbRaw(filePath, meta.folder, meta.publicId);
  const url = result.secure_url || result.url;

  if (!SKIP_MONGODB) {
    await DressGlbModel.findOneAndUpdate(
      { relativePath: meta.relativePath },
      {
        name: meta.name,
        category: meta.category,
        subcategory: meta.subcategory,
        folder: meta.folder,
        relativePath: meta.relativePath,
        cloudinaryUrl: url,
        publicId: result.public_id,
        bytes: result.bytes,
        uploadedAt: new Date(),
      },
      { upsert: true, new: true },
    );
  }

  const row = { relativePath: meta.relativePath, url, aliasOf: null };
  const aliases = catalogAliasesFromUpload(row);
  const outDir = path.join(__dirname, '../../data');
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, 'uploadBridalMahroonShort.json');
  fs.writeFileSync(outFile, JSON.stringify([row, ...aliases], null, 2));

  console.log('URL:', url);
  console.log('Wrote', outFile);
  if (!SKIP_MONGODB) {
    await disconnectDatabase();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
