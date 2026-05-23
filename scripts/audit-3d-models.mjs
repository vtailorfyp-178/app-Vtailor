import fs from 'fs';
import path from 'path';

const root = path.resolve(import.meta.dirname, '..', '..');
const frontend = path.join(root, 'app-Vtailor-frontend', 'app-vTailor');
const backend = path.join(root, 'app-Vtailor');

const PATH_RE = /['"]3d model\/[^'"]+\.glb['"]/g;

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, f.name);
    if (f.isDirectory()) walk(p, acc);
    else if (f.name.endsWith('.native.ts') || f.name === 'patiyalaDressGlb.native.ts') acc.push(p);
  }
  return acc;
}

const codePaths = new Set();
const glbDir = path.join(frontend, 'services', 'glb');
for (const file of walk(glbDir)) {
  const t = fs.readFileSync(file, 'utf8');
  let m;
  while ((m = PATH_RE.exec(t))) codePaths.add(m[0].slice(1, -1));
}

const cat = JSON.parse(
  fs.readFileSync(path.join(frontend, 'data', 'cloudinaryCatalog.json'), 'utf8'),
);
const catalogPaths = new Set(cat.map((x) => x.relativePath.toLowerCase()));

const modelRoot = path.join(backend, '3d model');
const localFiles = [];
function scanLocal(dir, base = '') {
  if (!fs.existsSync(dir)) return;
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = base ? `${base}/${f.name}` : f.name;
    const p = path.join(dir, f.name);
    if (f.isDirectory()) scanLocal(p, rel);
    else if (f.name.endsWith('.glb')) localFiles.push(`3d model/${rel.replace(/\\/g, '/')}`);
  }
}
scanLocal(modelRoot);
const localSet = new Set(localFiles.map((p) => p.toLowerCase()));

const codeArr = [...codePaths].sort();
const nativeOnly = codeArr.filter((p) => p.includes('/mobile/') || p.includes('/optimized/'));

function catalogHas(p) {
  const k = p.toLowerCase();
  if (catalogPaths.has(k)) return true;
  const opt = p.match(/^(.+)\/mobile\/(.+)\.glb$/i);
  if (opt) {
    const kebab = opt[2].replace(/ /g, '-');
    const guess = `${opt[1]}/optimized/optimized-${kebab}.glb`.toLowerCase();
    if (catalogPaths.has(guess)) return true;
  }
  return false;
}

const missingCatalog = codeArr.filter((p) => !catalogHas(p));
const missingLocal = codeArr.filter((p) => !localSet.has(p.toLowerCase()));
const unusedLocal = localFiles.filter(
  (p) => ![...codePaths].some((c) => c.toLowerCase() === p.toLowerCase()),
);

let totalBytes = 0;
for (const p of localFiles) {
  try {
    totalBytes += fs.statSync(path.join(backend, p.replace(/^3d model\//, '3d model\\').replace(/\//g, path.sep))).size;
  } catch {
    try {
      totalBytes += fs.statSync(path.join(backend, ...p.split('/'))).size;
    } catch {}
  }
}

const ur = path.join(backend, 'models-service', 'data', 'uploadResults.json');
const uploadCount = fs.existsSync(ur)
  ? JSON.parse(fs.readFileSync(ur, 'utf8')).filter((r) => r.url).length
  : 0;

const dupRoot = path.join(backend, 'app', '3dModels');
let dupCount = 0;
let dupBytes = 0;
if (fs.existsSync(dupRoot)) {
  function scanDup(d) {
    for (const f of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, f.name);
      if (f.isDirectory()) scanDup(p);
      else if (f.name.endsWith('.glb')) {
        dupCount++;
        dupBytes += fs.statSync(p).size;
      }
    }
  }
  scanDup(dupRoot);
}

const gi = fs.readFileSync(path.join(backend, '.gitignore'), 'utf8');

const report = {
  codeReferences: codeArr.length,
  catalogEntries: cat.length,
  uploadResultsWithUrl: uploadCount,
  localGlbCount: localFiles.length,
  localSizeGb: (totalBytes / 1024 ** 3).toFixed(2),
  duplicateApp3dModels: { files: dupCount, mb: Math.round(dupBytes / 1024 / 1024) },
  gitignoreBlocks3dModel: /3d model/i.test(gi),
  codeMissingCatalog: missingCatalog.length,
  codeMissingLocal: missingLocal.length,
  localNotInCode: unusedLocal.length,
  missingCatalogList: missingCatalog,
  missingLocalList: missingLocal.slice(0, 25),
};

const outPath = path.join(backend, 'scripts', 'audit-3d-report.json');
fs.writeFileSync(outPath, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
