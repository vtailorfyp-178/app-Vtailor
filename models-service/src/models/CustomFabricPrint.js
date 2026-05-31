const mongoose = require('mongoose');

const customFabricPrintSchema = new mongoose.Schema(
  {
    userId: { type: String, required: true, index: true, trim: true },
    printName: { type: String, default: 'Custom print', trim: true },
    printImage: { type: String, default: '', trim: true },
    cloudinaryUrl: { type: String, required: true, trim: true },
    publicId: { type: String, default: '', trim: true },
    uploadDate: { type: Date, default: Date.now },
  },
  { timestamps: true, collection: 'custom_fabric_prints', bufferCommands: false },
);

customFabricPrintSchema.index({ userId: 1, uploadDate: -1 });

module.exports =
  mongoose.models.CustomFabricPrint ||
  mongoose.model('CustomFabricPrint', customFabricPrintSchema);
