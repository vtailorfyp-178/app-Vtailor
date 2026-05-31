const express = require('express');
const multer = require('multer');
const crypto = require('crypto');
const CustomFabricPrint = require('../models/CustomFabricPrint');
const { uploadFabricPrintBuffer } = require('../config/cloudinary');
const { isDatabaseConnected } = require('../config/database');
const {
  CLOUDINARY_BASE_FOLDER,
  FABRIC_PRINTS_FOLDER,
  FABRIC_PRINT_MAX_BYTES,
  SKIP_MONGODB,
} = require('../config/env');

const router = express.Router();
const DB_SAVE_TIMEOUT_MS = 3000;

const ALLOWED_MIME = new Set(['image/jpeg', 'image/jpg', 'image/png', 'image/webp']);

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: FABRIC_PRINT_MAX_BYTES },
  fileFilter: (_req, file, cb) => {
    const mime = (file.mimetype || '').toLowerCase();
    if (ALLOWED_MIME.has(mime)) cb(null, true);
    else cb(new Error('Only JPG, JPEG, PNG, and WEBP images are allowed.'));
  },
});

function sanitizeUserId(raw) {
  return String(raw || 'anonymous')
    .trim()
    .slice(0, 128)
    .replace(/[^a-zA-Z0-9_-]/g, '_');
}

function buildPublicId(userId) {
  const stamp = Date.now();
  const rand = crypto.randomBytes(4).toString('hex');
  return `${userId}_${stamp}_${rand}`;
}

async function saveFabricPrintDoc(doc) {
  if (SKIP_MONGODB || !isDatabaseConnected()) {
    return null;
  }

  try {
    const saved = await Promise.race([
      CustomFabricPrint.create(doc),
      new Promise((_, reject) => {
        setTimeout(() => reject(new Error('MongoDB save timed out')), DB_SAVE_TIMEOUT_MS);
      }),
    ]);
    return saved;
  } catch (dbErr) {
    console.warn('[fabric-prints] MongoDB save skipped:', dbErr.message);
    return null;
  }
}

/** Ping route — confirms fabric-print upload API is mounted (avoids 404 from stale server). */
router.get('/ping', (_req, res) => {
  res.json({ ok: true, upload: '/fabric-prints/upload' });
});

/** POST /fabric-prints/upload — multipart field "file", body: userId, printName */
router.post('/upload', upload.single('file'), async (req, res, next) => {
  try {
    if (!req.file?.buffer?.length) {
      return res.status(400).json({ detail: 'No image file provided.' });
    }

    const userId = sanitizeUserId(req.body?.userId);
    const printName = String(req.body?.printName || req.file.originalname || 'Custom print')
      .trim()
      .slice(0, 120);
    const mime = (req.file.mimetype || 'image/jpeg').toLowerCase();
    const folder = `${CLOUDINARY_BASE_FOLDER}/${FABRIC_PRINTS_FOLDER}/${userId}`;
    const publicId = buildPublicId(userId);

    const result = await uploadFabricPrintBuffer(req.file.buffer, folder, publicId, mime);
    const cloudinaryUrl = result.secure_url || result.url;
    if (!cloudinaryUrl) {
      return res.status(502).json({ detail: 'Cloudinary upload did not return a URL.' });
    }

    const doc = {
      userId,
      printName,
      printImage: req.file.originalname || printName,
      cloudinaryUrl,
      publicId: result.public_id || publicId,
      uploadDate: new Date(),
    };

    let saved = doc;
    const dbSaved = await saveFabricPrintDoc(doc);
    if (dbSaved) saved = dbSaved;

    res.status(201).json({
      id: saved._id?.toString?.() || publicId,
      userId,
      printName,
      printImage: doc.printImage,
      cloudinaryUrl,
      publicId: doc.publicId,
      uploadDate: doc.uploadDate,
    });
  } catch (err) {
    next(err);
  }
});

/** GET /fabric-prints?userId=... */
router.get('/', async (req, res, next) => {
  try {
    const userId = sanitizeUserId(req.query.userId);
    if (!userId || userId === 'anonymous') {
      return res.status(400).json({ detail: 'userId query parameter is required.' });
    }
    if (SKIP_MONGODB || !isDatabaseConnected()) {
      return res.json({ prints: [] });
    }
    let prints = [];
    try {
      prints = await CustomFabricPrint.find({ userId })
        .sort({ uploadDate: -1 })
        .limit(40)
        .lean();
    } catch (dbErr) {
      console.warn('[fabric-prints] MongoDB list skipped:', dbErr.message);
    }
    res.json({
      prints: prints.map((p) => ({
        id: p._id.toString(),
        userId: p.userId,
        printName: p.printName,
        printImage: p.printImage,
        cloudinaryUrl: p.cloudinaryUrl,
        publicId: p.publicId,
        uploadDate: p.uploadDate,
      })),
    });
  } catch (err) {
    next(err);
  }
});

/** GET /fabric-prints/:id — must be after /ping and /upload */
router.get('/:id', async (req, res, next) => {
  try {
    const { id } = req.params;
    if (id === 'ping' || id === 'upload') {
      return res.status(404).json({ detail: 'Not found.' });
    }
    if (!/^[a-fA-F0-9]{24}$/.test(id)) {
      return res.status(400).json({ detail: 'Invalid print id.' });
    }
    if (SKIP_MONGODB || !isDatabaseConnected()) {
      return res.status(404).json({ detail: 'Print not found.' });
    }
    let doc = null;
    try {
      doc = await CustomFabricPrint.findById(req.params.id).lean();
    } catch (dbErr) {
      console.warn('[fabric-prints] MongoDB get skipped:', dbErr.message);
    }
    if (!doc) return res.status(404).json({ detail: 'Print not found.' });
    res.json({
      id: doc._id.toString(),
      userId: doc.userId,
      printName: doc.printName,
      printImage: doc.printImage,
      cloudinaryUrl: doc.cloudinaryUrl,
      publicId: doc.publicId,
      uploadDate: doc.uploadDate,
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
