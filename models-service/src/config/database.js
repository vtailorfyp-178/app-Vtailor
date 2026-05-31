const mongoose = require('mongoose');
const { MONGODB_URL, MONGO_DB_NAME, SKIP_MONGODB } = require('./env');

let connected = false;

function isDatabaseConnected() {
  return !SKIP_MONGODB && connected && mongoose.connection.readyState === 1;
}

async function connectDatabase() {
  if (SKIP_MONGODB) {
    console.log('[db] SKIP_MONGODB=true — MongoDB disabled for this run');
    return null;
  }

  if (connected) return mongoose.connection;

  const masked = MONGODB_URL.replace(/\/\/([^:]+):([^@]+)@/, '//$1:***@');
  console.log(`[db] Connecting to ${masked} (db: ${MONGO_DB_NAME})`);

  try {
    await mongoose.connect(MONGODB_URL, {
      dbName: MONGO_DB_NAME,
      serverSelectionTimeoutMS: 15_000,
    });
    connected = true;
    console.log('[db] MongoDB connected');
    return mongoose.connection;
  } catch (err) {
    mongoose.set('bufferCommands', false);
    console.error('\n[db] MongoDB connection failed.');
    console.error('  Fix one of these:');
    console.error('  1) Use Atlas: copy MONGODB_URL from app-Vtailor\\.env into models-service\\.env');
    console.error('     OR remove MONGODB_URL=localhost from models-service\\.env');
    console.error('  2) Local Docker: cd app-Vtailor && docker compose up -d mongo');
    console.error('  3) Upload without DB: npm run upload:glbs -- --skip-mongo');
    console.error('     Then later: npm run seed:from-results\n');
    throw err;
  }
}

async function disconnectDatabase() {
  if (!connected) return;
  await mongoose.disconnect();
  connected = false;
}

module.exports = { connectDatabase, disconnectDatabase, isDatabaseConnected };
