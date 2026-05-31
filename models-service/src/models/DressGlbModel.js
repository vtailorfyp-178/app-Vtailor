const mongoose = require('mongoose');

/**
 * Cloudinary-backed 3D dress GLB catalog.
 * `relativePath` matches frontend resolver paths (e.g. `3d model/3d long frock/mobile/foo.glb`).
 */
const dressGlbSchema = new mongoose.Schema(
  {
    name: { type: String, required: true, index: true },
    category: { type: String, required: true, index: true },
    subcategory: { type: String, required: true, default: 'root' },
    folder: { type: String, required: true },
    relativePath: { type: String, required: true, unique: true, index: true },
    /** Lowercase normalized key for reliable lookups */
    relativePathKey: { type: String, required: true, unique: true, index: true },
    cloudinaryUrl: { type: String, required: true },
    publicId: { type: String, required: true },
    bytes: { type: Number },
    uploadedAt: { type: Date, default: Date.now },
    /** Trouser shirt / bell bottom (optional — legacy rows omit these). */
    variation: { type: String, index: true },
    neckType: { type: String, index: true },
    sleeveType: { type: String, index: true },
    previewImage: { type: String },
    thumbnail: { type: String },
    colors: [{ type: String }],
  },
  { timestamps: true },
);

dressGlbSchema.index({ category: 1, subcategory: 1 });

module.exports =
  mongoose.models.DressGlbModel || mongoose.model('DressGlbModel', dressGlbSchema, 'dress_glb_models');
