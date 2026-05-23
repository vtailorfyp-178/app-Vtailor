/**
 * Test Cloudinary credentials before uploading 477 files.
 * Usage: npm run verify:cloudinary
 */

const { cloudinary } = require('../config/cloudinary');
const { CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY } = require('../config/env');

async function main() {
  const name = (CLOUDINARY_CLOUD_NAME || '').trim();
  console.log('Cloud name from .env:', name);
  console.log('API key (last 4):', `***${String(CLOUDINARY_API_KEY || '').slice(-4)}`);

  if (!name) {
    console.error('\nCLOUDINARY_CLOUD_NAME is empty in models-service/.env');
    process.exit(1);
  }

  if (name.startsWith('adb') && name.length > 3) {
    console.warn(
      '\nWarning: cloud name starts with "adb" — often a typo for "d..." (extra letter "a").',
    );
    console.warn('Dashboard shows Cloud name like: dxxxxxxxx  (copy exactly, no spaces)\n');
  }

  try {
    const ping = await cloudinary.api.ping();
    console.log('\nCloudinary OK:', ping);
    console.log(
      '\nNext: npm run upload:glbs:no-mongo',
    );
    process.exit(0);
  } catch (err) {
    const msg =
      err?.error?.message ||
      err?.message ||
      (typeof err?.error === 'string' ? err.error : null) ||
      JSON.stringify(err?.error || err);
    console.error('\nCloudinary FAILED:', msg);

    if (/invalid cloud_name/i.test(msg)) {
      console.error(`
Fix CLOUDINARY_CLOUD_NAME in models-service/.env:

  1. Login: https://console.cloudinary.com/
  2. Dashboard → Product environment credentials
  3. Copy "Cloud name" EXACTLY (example: dabc123xyz)
  4. Paste into .env — NOT api key, NOT folder name
  5. Run again: npm run verify:cloudinary

Common mistake: adb7k22ekb  →  should be db7k22ekb (or whatever dashboard shows)
`);
    } else if (/cloud_name mismatch|invalid api_key|401|403/i.test(msg)) {
      console.error(`
API Key / Secret do not match Cloud name.
Copy ALL THREE from the SAME Cloudinary dashboard block:
  Cloud name, API Key, API Secret
Do not mix values from ChatGPT / old notes (e.g. adb7k22ekb vs db7k22ekb).
`);
    }

    process.exit(1);
  }
}

main();
