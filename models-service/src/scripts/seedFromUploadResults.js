/**
 * Import uploadResults.json into MongoDB without re-uploading to Cloudinary.
 * Usage: npm run seed:from-results
 */

const fs = require('fs');
const path = require('path');
const { connectDatabase, disconnectDatabase } = require('../config/database');
const { RESULTS_DIR } = require('../config/env');
const DressGlbModel = require('../models/DressGlbModel');
const { normalizeRelativePath } = require('../utils/pathMetadata');

async function main() {
  const file = path.join(RESULTS_DIR, 'uploadResults.json');
  if (!fs.existsSync(file)) {
    console.error('Missing', file, '— run npm run upload:glbs first');
    process.exit(1);
  }

  const rows = JSON.parse(fs.readFileSync(file, 'utf8'));
  await connectDatabase();

  for (const row of rows) {
    if (!row.relativePath || !row.url) continue;
    await DressGlbModel.findOneAndUpdate(
      { relativePath: row.relativePath },
      {
        name: row.name,
        category: row.category,
        subcategory: row.subcategory || 'root',
        folder: row.folder,
        relativePath: row.relativePath,
        relativePathKey: normalizeRelativePath(row.relativePath),
        cloudinaryUrl: row.url,
        publicId: row.folder + '/' + row.name.replace(/\.glb$/i, ''),
      },
      { upsert: true },
    );
  }

  console.log(`Seeded ${rows.length} document(s) from uploadResults.json`);
  await disconnectDatabase();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
