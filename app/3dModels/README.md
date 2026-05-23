# 3D model static assets

Served at: `http://<host>:8000/3dModels/3d%20model/...`

## One-time setup (from repo)

```powershell
cd app-Vtailor-frontend\app-vTailor
npm run sync:3dmodels-backend
```

This copies from `app-Vtailor/3d model/` → `app-Vtailor/app/3dModels/3d model/`.

Restart API after sync: `cd app-Vtailor` → `.\start-api.ps1`

Check: `http://localhost:8000/health` should show `"glb_models": 290` (approx).
