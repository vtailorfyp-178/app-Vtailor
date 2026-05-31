/**
 * Trouser shirt → Tulip trouser catalog (API + upload metadata).
 * GLB paths match frontend `tulipTrouserDressGlb.*` resolver.
 */

const CATEGORY = 'casual';
const SUB_CATEGORY = 'trouser-shirt';
const VARIATION = 'tulip-trouser';

const NECK_TYPES = [
  { id: 'round', name: 'Round neck' },
  { id: 'collar', name: 'Collar neck' },
  { id: 'keyhole', name: 'Collar keyhole neck' },
];

const SLEEVE_TYPES = [
  { id: 'full', name: 'Pleated full sleeves' },
  { id: 'bell', name: 'Pleated bell sleeves' },
  { id: 'puff', name: 'Puff/balloon sleeves' },
];

/** UI ids → optimized GLB filename (under tulip-trouser/optimized/). */
const GLB_FILENAME_BY_NECK_SLEEVE = {
  round: {
    full: 'round-neck-full-sleeve.glb',
    bell: 'round-neck-bell-sleeve.glb',
    puff: 'round-neck-puff-sleeve.glb',
  },
  collar: {
    full: 'collar-neck-full-sleeve.glb',
    bell: 'collar-neck-bell-sleeve.glb',
    puff: 'collar-neck-puff-sleeve.glb',
  },
  keyhole: {
    full: 'keyhole-neck-full-sleeve.glb',
    bell: 'keyhole-neck-bell-sleeve.glb',
    puff: 'keyhole-neck-puff-sleeve.glb',
  },
};

const TULIP_TROUSER_OPT_PREFIX = '3d model/3d trouser shirt/tulip-trouser/optimized';

function relativePathForNeckSleeve(neckId, sleeveId) {
  const file = GLB_FILENAME_BY_NECK_SLEEVE[neckId]?.[sleeveId];
  if (!file) return null;
  return `${TULIP_TROUSER_OPT_PREFIX}/${file}`;
}

function listTulipTrouserVariants() {
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

const SOURCE_NAME_HINTS = [
  { neck: 'round', sleeve: 'full', patterns: [/round.*full/i, /full.*round/i] },
  { neck: 'round', sleeve: 'bell', patterns: [/round.*bell/i, /bell.*round/i] },
  { neck: 'round', sleeve: 'puff', patterns: [/round.*(puff|balloon)/i] },
  { neck: 'collar', sleeve: 'full', patterns: [/collar.*full/i, /color.*full/i, /full.*collar/i] },
  { neck: 'collar', sleeve: 'bell', patterns: [/collar.*bell/i, /color.*bell/i] },
  { neck: 'collar', sleeve: 'puff', patterns: [/collar.*(puff|balloon)/i, /color.*(puff|balloon)/i] },
  { neck: 'keyhole', sleeve: 'full', patterns: [/keyhole.*full/i] },
  { neck: 'keyhole', sleeve: 'bell', patterns: [/keyhole.*bell/i] },
  { neck: 'keyhole', sleeve: 'puff', patterns: [/keyhole.*(puff|balloon)/i] },
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
  TULIP_TROUSER_OPT_PREFIX,
  relativePathForNeckSleeve,
  listTulipTrouserVariants,
  matchSourceToVariant,
};
