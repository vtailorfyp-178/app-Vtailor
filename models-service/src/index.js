const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const { PORT, NODE_ENV } = require('./config/env');
const { connectDatabase } = require('./config/database');
const { readJsonCatalog } = require('./services/catalogStore');
const modelsRouter = require('./routes/models.routes');
const bellBottomRouter = require('./routes/bellBottom.routes');
const tulipTrouserRouter = require('./routes/tulipTrouser.routes');
const fabricPrintsRouter = require('./routes/fabricPrints.routes');

const app = express();

app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: '1mb' }));
if (NODE_ENV !== 'test') {
  app.use(morgan('dev'));
}

app.get('/health', async (_req, res) => {
  const jsonCatalog = readJsonCatalog();
  res.json({
    status: 'ok',
    service: 'vtailor-models-service',
    jsonCatalogCount: jsonCatalog.length,
  });
});

app.use('/models', modelsRouter);
app.use('/bell-bottom', bellBottomRouter);
app.use('/tulip-trouser', tulipTrouserRouter);
app.use('/fabric-prints', fabricPrintsRouter);

app.use((err, _req, res, _next) => {
  console.error('[models-service]', err);
  res.status(500).json({ detail: err.message || 'Internal server error' });
});

async function start() {
  try {
    await connectDatabase();
  } catch (err) {
    const mongoose = require('mongoose');
    mongoose.set('bufferCommands', false);
    console.warn('[startup] Running without MongoDB — fabric prints still upload to Cloudinary');
    console.warn('[startup]', err.message);
  }

  const jsonCount = readJsonCatalog().length;
  if (jsonCount > 0) {
    console.log(`[startup] JSON catalog ready: ${jsonCount} model(s) from uploadResults.json`);
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Models API: http://0.0.0.0:${PORT}`);
    console.log(`  GET  http://localhost:${PORT}/health`);
    console.log(`  GET  http://localhost:${PORT}/models`);
    console.log(`  POST http://localhost:${PORT}/fabric-prints/upload`);
    console.log(`  Phone: http://YOUR_PC_IP:${PORT}/health`);
  });
}

start();
