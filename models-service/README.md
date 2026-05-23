# vTailor Models Service (Node.js + Express + Cloudinary)

Production API for 3D GLB assets stored on **Cloudinary** and indexed in **MongoDB**.

## Local 3D model root (this repo)

```
C:\Users\HP\Desktop\project\app-Vtailor\3d model
```

Set in `.env`:

```
MODEL_ROOT_PATH=../3d model
```

## Folder layout

| Path | Purpose |
|------|---------|
| `models-service/src/config/` | Cloudinary, MongoDB, env |
| `models-service/src/models/` | Mongoose schema |
| `models-service/src/routes/` | `GET /models` |
| `models-service/src/scripts/` | Upload + seed |
| `models-service/data/` | `uploadResults.json`, `uploadFailed.json` |

## Setup

```powershell
cd C:\Users\HP\Desktop\project\app-Vtailor\models-service
copy .env.example .env
# Edit .env: Cloudinary + MONGODB_URL (copy from app-Vtailor\.env)
npm install
```

## Upload all GLBs (safe, sequential)

```powershell
npm run upload:glbs
```

- `resource_type: raw`
- Cloudinary folder: `vtailor-models/<category>/<subcategory>/`
- 1.5s delay between files (configurable)
- Max 2 retries; failures → `data/uploadFailed.json`
- Success → `data/uploadResults.json` + MongoDB upsert

## Run API

```powershell
npm start
# GET http://localhost:3001/models
# GET http://localhost:3001/models/by-path?path=3d%20model%2F...
```

## Frontend

Set in `app-vTailor/.env`:

```
EXPO_PUBLIC_MODELS_API_URL=http://YOUR_PC_IP:3001
```

Expo web dev can proxy via Metro (see `metro.config.js`).
