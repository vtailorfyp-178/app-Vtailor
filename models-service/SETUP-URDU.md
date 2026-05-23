# Models service — setup (mobile ke liye)

## Error jo aaya tha

`ECONNREFUSED 127.0.0.1:27017` = MongoDB **localhost** par nahi chal raha.

Tumhari asli MongoDB **Atlas** par hai (`app-Vtailor\.env` mein).

## Upload fail: Invalid cloud_name / cloud_name mismatch

**Matlab:** `.env` mein Cloudinary ki 3 values **galat ya mix** hain.

GPT ne kabhi `adb7k22ekb` likha — shayad sahi naam **`db7k22ekb`** ho (dashboard dekho).

**Fix:**

1. https://console.cloudinary.com/ → login  
2. **Dashboard** → **API Keys** (Product environment credentials)  
3. Ek hi jagah se copy karo:
   - **Cloud name** (chhota naam, e.g. `db7k22ekb` ya `dxxxxx`)
   - **API Key**
   - **API Secret**
4. `models-service\.env` mein teeno paste karo (purane hata kar)
5. Test:

```powershell
npm run verify:cloudinary
```

Jab `Cloudinary OK` aaye tab:

```powershell
npm run upload:glbs:no-mongo
```

**File size too large (31MB):** Cloudinary free plan = **10MB max**.  
Script `original/` (30MB+) skip karta hai. **Grarah:** app ab `optimized/` use karti hai (textures embedded, ~2MB). Texture-less Tripo `mobile/` upload nahi hota. Run: `npm run upload:grarah-optimized` phir frontend par `node scripts/sync-cloudinary-catalog.mjs`.

---

## Mongo fix (pehle wala)

`models-service\.env` kholo aur **yeh lines hata do ya comment karo**:

```
MONGODB_URL=mongodb://localhost:27017
MONGO_DB_NAME=vtailor
```

Cloudinary keys wahan rehne do. Save karo.

Ab dubara:

```powershell
cd C:\Users\HP\Desktop\project\app-Vtailor\models-service
npm run upload:glbs
```

Script ab `app-Vtailor\.env` se Atlas URL le legi.

---

## Agar Mongo / Atlas fail ho (querySrv ECONNREFUSED)

**Pehle Cloudinary upload bina Mongo ke chalao** (~12 min, 477 files):

```powershell
npm run upload:glbs:no-mongo
```

Yeh `data/uploadResults.json` banayega.

**API start** (Mongo optional — JSON se catalog milega):

```powershell
npm start
```

Browser: `http://localhost:3001/models` — agar JSON upload ho chuka ho to list dikhegi.

Baad mein Atlas theek ho to:

```powershell
npm run seed:from-results
```

---

## Upload ke baad (mobile)

### Terminal 1 — Models API

```powershell
cd C:\Users\HP\Desktop\project\app-Vtailor\models-service
npm start
```

Browser: `http://localhost:3001/models` — list aani chahiye.

### Terminal 2 — FastAPI (login / orders)

```powershell
cd C:\Users\HP\Desktop\project\app-Vtailor
.\start-api.ps1
```

### Terminal 3 — Expo (phone)

`app-vTailor\.env`:

```env
EXPO_PUBLIC_MODELS_API_URL=http://YOUR_PC_WIFI_IP:3001
EXPO_PUBLIC_USE_CLOUDINARY_MODELS=true
EXPO_PUBLIC_API_BASE_URL=http://YOUR_PC_WIFI_IP:8000/app/api/v1
```

`YOUR_PC_WIFI_IP` = `ipconfig` → IPv4 (e.g. 192.168.1.6)

```powershell
cd C:\Users\HP\Desktop\project\app-Vtailor-frontend\app-vTailor
npx expo start --lan
```

Phone aur PC **same Wi‑Fi**.

Windows Firewall: ports **3001** aur **8000** allow.

---

## Checklist

- [ ] `models-service\.env` — localhost Mongo lines removed
- [ ] `npm run upload:glbs` — success / `data/uploadResults.json`
- [ ] `npm start` — `GET /models` works
- [ ] Phone `.env` — PC IP + port 3001
- [ ] 3D customize screen — dress Cloudinary se load
