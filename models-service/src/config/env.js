const path = require('path');
const dotenv = require('dotenv');

const modelsServiceRoot = path.resolve(__dirname, '../..');
const parentEnv = path.join(modelsServiceRoot, '../.env');
const localEnv = path.join(modelsServiceRoot, '.env');

// Parent first (MongoDB Atlas), then models-service/.env wins for Cloudinary keys.
dotenv.config({ path: parentEnv });
dotenv.config({ path: localEnv, override: true });

function required(name, fallback) {
  const v = process.env[name] ?? fallback;
  if (v === undefined || v === '') {
    throw new Error(`Missing required env: ${name}`);
  }
  return v;
}

const modelRootRaw = process.env.MODEL_ROOT_PATH || '../3d model';
const MODEL_ROOT_PATH = path.isAbsolute(modelRootRaw)
  ? modelRootRaw
  : path.resolve(modelsServiceRoot, modelRootRaw);

/** True when upload/API should skip Mongo (JSON-only mode). */
const SKIP_MONGODB =
  process.env.SKIP_MONGODB === 'true' ||
  process.env.SKIP_MONGODB === '1' ||
  process.argv.includes('--skip-mongo');

function resolveMongoUrl() {
  const url = (process.env.MONGODB_URL || '').trim();
  if (url && !url.includes('localhost:27017') && !url.includes('127.0.0.1:27017')) {
    return url;
  }
  // Parent .env loaded first; if local .env still has localhost, prefer parent Atlas URL
  dotenv.config({ path: parentEnv, override: true });
  const parentUrl = (process.env.MONGODB_URL || '').trim();
  if (parentUrl) return parentUrl;
  return url || 'mongodb://127.0.0.1:27017';
}

const MONGODB_URL = resolveMongoUrl();
const MONGO_DB_NAME = process.env.MONGO_DB_NAME || 'app_vtailor_db';

module.exports = {
  NODE_ENV: process.env.NODE_ENV || 'development',
  PORT: Number(process.env.MODELS_API_PORT || 3001),
  MODEL_ROOT_PATH,
  MONGODB_URL,
  MONGO_DB_NAME,
  SKIP_MONGODB,
  CLOUDINARY_CLOUD_NAME: required('CLOUDINARY_CLOUD_NAME'),
  CLOUDINARY_API_KEY: required('CLOUDINARY_API_KEY'),
  CLOUDINARY_API_SECRET: required('CLOUDINARY_API_SECRET'),
  CLOUDINARY_BASE_FOLDER: process.env.CLOUDINARY_BASE_FOLDER || 'vtailor-models',
  FABRIC_PRINTS_FOLDER: process.env.FABRIC_PRINTS_FOLDER || 'vtailor-fabric-prints',
  FABRIC_PRINT_MAX_BYTES: Number(process.env.FABRIC_PRINT_MAX_BYTES || 8 * 1024 * 1024),
  UPLOAD_DELAY_MS: Number(process.env.UPLOAD_DELAY_MS || 1500),
  UPLOAD_MAX_RETRIES: Number(process.env.UPLOAD_MAX_RETRIES || 2),
  UPLOAD_BATCH_SIZE: Math.max(1, Number(process.env.UPLOAD_BATCH_SIZE || 1)),
  /** Cloudinary free plan: 10MB per raw file */
  UPLOAD_MAX_FILE_BYTES: Number(process.env.UPLOAD_MAX_FILE_BYTES || 10 * 1024 * 1024),
  UPLOAD_SKIP_ORIGINAL: process.env.UPLOAD_SKIP_ORIGINAL !== 'false',
  UPLOAD_SKIP_OPTIMIZED_IF_MOBILE: process.env.UPLOAD_SKIP_OPTIMIZED_IF_MOBILE !== 'false',
  RESULTS_DIR: path.resolve(modelsServiceRoot, 'data'),
  parentEnvPath: parentEnv,
  localEnvPath: localEnv,
};
