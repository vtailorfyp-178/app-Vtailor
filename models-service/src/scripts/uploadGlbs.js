/**
 * Scan MODEL_ROOT_PATH, upload GLBs to Cloudinary (raw), upsert MongoDB, write JSON reports.
 *
 * Skips original/ 30MB files (Cloudinary free limit 10MB). Uploads mobile/ + small files.
 *
 * Usage: npm run upload:glbs:no-mongo
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
  UPLOAD_BATCH_SIZE,
  UPLOAD_MAX_FILE_BYTES,
  UPLOAD_SKIP_ORIGINAL,
  UPLOAD_SKIP_OPTIMIZED_IF_MOBILE,
  RESULTS_DIR,
  SKIP_MONGODB,
  MONGO_DB_NAME,
} = require('../config/env');
const DressGlbModel = require('../models/DressGlbModel');
const { scanGlbFiles } = require('../utils/scanGlbs');
const { metadataFromAbsolute, normalizeRelativePath } = require('../utils/pathMetadata');
const {
  filterGlbsForUpload,
  catalogAliasesFromUpload,
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
      const msg = err?.message || String(err);
      if (/file size too large/i.test(msg)) {
        throw err;
      }
      if (attempt < UPLOAD_MAX_RETRIES) {
        console.warn(`  retry ${attempt + 1}/${UPLOAD_MAX_RETRIES}: ${msg}`);
        await sleep(UPLOAD_DELAY_MS);
      }
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
      relativePathKey: normalizeRelativePath(meta.relativePath),
      cloudinaryUrl: url,
      publicId: cloudinaryResult.public_id,
      bytes: cloudinaryResult.bytes,
      uploadedAt: new Date(),
    },
    { upsert: true, new: true },
  );
  return url;
}

async function verifyCloudinaryOrExit() {
  console.log('Cloudinary cloud_name:', CLOUDINARY_CLOUD_NAME);
  try {
    await cloudinary.api.ping();
    console.log('Cloudinary credentials OK\n');
  } catch (err) {
    const msg = err.message || String(err);
    console.error('\nCloudinary check FAILED — fix .env before uploading.');
    console.error('Error:', msg);
    process.exit(1);
  }
}

function isCloudinaryConfigError(err) {
  const msg = (err && err.message) || String(err);
  return /invalid cloud_name|invalid api_key|401|403/i.test(msg);
}

async function main() {
  await verifyCloudinaryOrExit();

  console.log('Model root:', MODEL_ROOT_PATH);
  if (!fs.existsSync(MODEL_ROOT_PATH)) {
    console.error('MODEL_ROOT_PATH does not exist. Set MODEL_ROOT_PATH in .env');
    process.exit(1);
  }

  fs.mkdirSync(RESULTS_DIR, { recursive: true });

  const allFiles = scanGlbFiles(MODEL_ROOT_PATH);
  const { toUpload, skipped } = filterGlbsForUpload(allFiles, MODEL_ROOT_PATH, {
    maxBytes: UPLOAD_MAX_FILE_BYTES,
    skipOriginal: UPLOAD_SKIP_ORIGINAL,
    skipOptimizedIfMobile: UPLOAD_SKIP_OPTIMIZED_IF_MOBILE,
  });

  console.log(`Found ${allFiles.length} .glb on disk`);
  console.log(`Will upload ${toUpload.length} (skip ${skipped.length}: original/too large)`);
  console.log(`Max file size: ${(UPLOAD_MAX_FILE_BYTES / (1024 * 1024)).toFixed(0)}MB per Cloudinary plan\n`);

  if (SKIP_MONGODB) {
    console.log('MongoDB skipped — results only in data/uploadResults.json');
  } else {
    console.log(`MongoDB: ${MONGO_DB_NAME}`);
  }

  await connectDatabase();

  const successes = [];
  const failures = [];
  const total = toUpload.length;
  let index = 0;

  while (index < total) {
    const batch = toUpload.slice(index, index + UPLOAD_BATCH_SIZE);
    index += UPLOAD_BATCH_SIZE;

    for (const filePath of batch) {
      const meta = metadataFromAbsolute(filePath, MODEL_ROOT_PATH, CLOUDINARY_BASE_FOLDER);
      const n = successes.length + failures.length + 1;
      process.stdout.write(`[${n}/${total}] ${meta.relativePath} … `);

      try {
        const result = await uploadWithRetry(filePath, meta.folder, meta.publicId);
        const url = await upsertModel(meta, result);
        for (const row of catalogAliasesFromUpload(meta, url)) {
          successes.push(row);
        }
        console.log('ok');
      } catch (err) {
        failures.push({
          name: meta.name,
          folder: meta.folder,
          category: meta.category,
          relativePath: meta.relativePath,
          filePath,
          error: err.message || String(err),
        });
        console.log('FAILED');
        if (isCloudinaryConfigError(err) && failures.length >= 3 && successes.length === 0) {
          console.error('\nStopping: Cloudinary config error.\n');
          break;
        }
      }

      const done = successes.length + failures.length;
      if (done < total) {
        await sleep(UPLOAD_DELAY_MS);
      }
    }
  }

  const resultsPath = path.join(RESULTS_DIR, 'uploadResults.json');
  const failedPath = path.join(RESULTS_DIR, 'uploadFailed.json');
  const skippedPath = path.join(RESULTS_DIR, 'uploadSkipped.json');

  fs.writeFileSync(resultsPath, JSON.stringify(successes, null, 2), 'utf8');
  fs.writeFileSync(failedPath, JSON.stringify(failures, null, 2), 'utf8');
  fs.writeFileSync(skippedPath, JSON.stringify(skipped, null, 2), 'utf8');

  console.log('\nDone.');
  console.log(`  Uploaded: ${successes.length} catalog entries → ${resultsPath}`);
  console.log(`  Skipped:  ${skipped.length} (original/too large) → ${skippedPath}`);
  console.log(`  Failed:   ${failures.length} → ${failedPath}`);

  await disconnectDatabase();
  process.exit(failures.length > 0 ? 1 : 0);
}

main().catch(async (err) => {
  console.error(err);
  await disconnectDatabase().catch(() => {});
  process.exit(1);
});
