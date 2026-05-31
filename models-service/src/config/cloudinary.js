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

/**
 * Upload customer fabric print — optimized image for 3D texture mapping.
 * @param {Buffer} buffer File bytes from multer
 * @param {string} folder Cloudinary folder
 * @param {string} publicId Unique public id (no extension)
 * @param {string} mime e.g. image/jpeg
 */
function uploadFabricPrintBuffer(buffer, folder, publicId, mime = 'image/jpeg') {
  return new Promise((resolve, reject) => {
    const stream = cloudinary.uploader.upload_stream(
      {
        resource_type: 'image',
        folder,
        public_id: publicId,
        overwrite: true,
        unique_filename: false,
        use_filename: false,
        quality: 'auto:good',
        fetch_format: 'auto',
        flags: 'preserve_transparency',
      },
      (err, result) => {
        if (err) reject(err);
        else resolve(result);
      },
    );
    stream.end(buffer);
  });
}

module.exports = { cloudinary, uploadGlbRaw, uploadFabricPrintBuffer };
