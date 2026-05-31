/**
 * Trouser shirt → Bell bottom catalog (API + upload metadata).
 * GLB paths match frontend `bellBottomDressGlb.*` resolver.
 */

const CATEGORY = 'casual';
const SUB_CATEGORY = 'trouser-shirt';
const VARIATION = 'bell-bottom';

const NECK_TYPES = [
  { id: 'round', name: 'Round neck' },
  { id: 'collar', name: 'Collar neck' },
  { id: 'keyhole', name: 'Round keyhole neck' },
];

const SLEEVE_TYPES = [
  { id: 'straight', name: 'Pleated straight sleeves' },
  { id: 'puff', name: 'Puff/balloon sleeves' },
  { id: 'flared-bell', name: 'Pleated flared bell sleeves' },
];

/** UI ids → optimized GLB filename (under bell-bottom/optimized/). */
const GLB_FILENAME_BY_NECK_SLEEVE = {
  round: {
    straight: 'round-neck-straight-sleeve.glb',
    puff: 'round-neck-puff-sleeve.glb',
    'flared-bell': 'round-neck-flared-bell-sleeve.glb',
  },
  collar: {
    straight: 'collar-neck-straight-sleeve.glb',
    puff: 'collar-neck-puff-sleeve.glb',
    'flared-bell': 'collar-neck-flared-bell-sleeve.glb',
  },
  keyhole: {
    straight: 'keyhole-straight-sleeve.glb',
    puff: 'keyhole-puff-sleeve.glb',
    'flared-bell': 'keyhole-flared-bell-sleeve.glb',
  },
};

const BELL_BOTTOM_OPT_PREFIX = '3d model/3d trouser shirt/bell-bottom/optimized';

function relativePathForNeckSleeve(neckId, sleeveId) {
  const file = GLB_FILENAME_BY_NECK_SLEEVE[neckId]?.[sleeveId];
  if (!file) return null;
  return `${BELL_BOTTOM_OPT_PREFIX}/${file}`;
}

/** All 9 variant rows for upload seeding / API. */
function listBellBottomVariants() {
  const rows = [];
  for (const neck of NECK_TYPES) {
    for (const sleeve of SLEEVE_TYPES) {
      const relativePath = relativePathForNeckSleeve(neck.id, sleeve.id);
      rows.push({
        category: CATEGORY,
        subCategory: SUB_CATEGORY,
        variation: VARIATION,
        neckType: neck.id,
        sleeveType: sleeve.id,
        relativePath,
        glbFileName: GLB_FILENAME_BY_NECK_SLEEVE[neck.id][sleeve.id],
        previewImage: null,
        thumbnail: null,
        colors: [],
      });
    }
  }
  return rows;
}

/** Loose source-name patterns → { neckId, sleeveId } for compress script. */
const SOURCE_NAME_HINTS = [
  { neck: 'round', sleeve: 'straight', patterns: [/round.*straight/i, /straight.*round/i] },
  { neck: 'round', sleeve: 'puff', patterns: [/round.*puff/i, /round.*balloon/i, /puff.*round/i] },
  {
    neck: 'round',
    sleeve: 'flared-bell',
    patterns: [/round.*flared/i, /round.*bell/i, /flared.*round/i],
  },
  { neck: 'collar', sleeve: 'straight', patterns: [/collar.*straight/i, /straight.*collar/i] },
  { neck: 'collar', sleeve: 'puff', patterns: [/collar.*puff/i, /collar.*balloon/i] },
  {
    neck: 'collar',
    sleeve: 'flared-bell',
    patterns: [/collar.*flared/i, /collar.*bell/i, /flared.*collar/i],
  },
  { neck: 'keyhole', sleeve: 'straight', patterns: [/keyhole.*straight/i, /straight.*keyhole/i] },
  { neck: 'keyhole', sleeve: 'puff', patterns: [/keyhole.*puff/i, /keyhole.*balloon/i] },
  {
    neck: 'keyhole',
    sleeve: 'flared-bell',
    patterns: [/keyhole.*flared/i, /keyhole.*bell/i, /flared.*keyhole/i],
  },
];

function matchSourceToVariant(sourceBaseName) {
  const base = String(sourceBaseName || '').replace(/\.glb$/i, '');
  for (const hint of SOURCE_NAME_HINTS) {
    if (hint.patterns.some((re) => re.test(base))) {
      return { neckId: hint.neck, sleeveId: hint.sleeve };
    }
  }
  const exact = base
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
  for (const neck of NECK_TYPES) {
    for (const sleeve of SLEEVE_TYPES) {
      const out = GLB_FILENAME_BY_NECK_SLEEVE[neck.id][sleeve.id].replace(/\.glb$/i, '');
      if (exact === out) return { neckId: neck.id, sleeveId: sleeve.id };
    }
  }
  return null;
}

module.exports = {
  CATEGORY,
  SUB_CATEGORY,
  VARIATION,
  NECK_TYPES,
  SLEEVE_TYPES,
  GLB_FILENAME_BY_NECK_SLEEVE,
  BELL_BOTTOM_OPT_PREFIX,
  relativePathForNeckSleeve,
  listBellBottomVariants,
  matchSourceToVariant,
};
