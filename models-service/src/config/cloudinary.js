const { v2: cloudinary } = require('cloudinary');
const {
  CLOUDINARY_CLOUD_NAME,
  CLOUDINARY_API_KEY,
  CLOUDINARY_API_SECRET,
} = require('./env');

cloudinary.config({
  cloud_name: CLOUDINARY_CLOUD_NAME,
  api_key: CLOUDINARY_API_KEY,
  api_secret: CLOUDINARY_API_SECRET,
  secure: true,
});

/**
 * Upload a single GLB as raw asset.
 * @param {string} filePath Absolute path on disk
 * @param {string} folder Cloudinary folder (category/subcategory)
 * @param {string} publicId Filename without extension (sanitized)
 */
async function uploadGlbRaw(filePath, folder, publicId) {
  return cloudinary.uploader.upload(filePath, {
    resource_type: 'raw',
    folder,
    public_id: publicId,
    overwrite: true,
    unique_filename: false,
    use_filename: false,
  });
}

module.exports = { cloudinary, uploadGlbRaw };
