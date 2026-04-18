const ROOM_THEME_SPECS = {
  library: {
    key: 'library',
    label: 'Archive Room',
    subtitle: 'Memory Wing',
    accent: 0x8B9DC3,
    accentSoft: 0xC8D3E8,
    accentDark: 0x5F7296,
    portal: 0x6B8EB5,
    badgeText: 'LIB',
  },
  observatory: {
    key: 'observatory',
    label: 'Analysis Room',
    subtitle: 'Review Hall',
    accent: 0x7EC8A4,
    accentSoft: 0xBFE4D1,
    accentDark: 0x519677,
    portal: 0x5BA680,
    badgeText: 'OBS',
  },
  alchemy: {
    key: 'alchemy',
    label: 'Debug Lab',
    subtitle: 'Test Bench',
    accent: 0xE9AD58,
    accentSoft: 0xF5D19C,
    accentDark: 0xB5832E,
    portal: 0xD4923D,
    badgeText: 'LAB',
  },
  workshop: {
    key: 'workshop',
    label: 'Code Workshop',
    subtitle: 'Build Floor',
    accent: 0x4A90D9,
    accentSoft: 0xA5C9EC,
    accentDark: 0x2C6EA0,
    portal: 0x3D7FC4,
    badgeText: 'DEV',
  },
};

const ROOM_THEME_ORDER = Object.keys(ROOM_THEME_SPECS);

function stableHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function roomTitleFromId(roomId) {
  return roomId.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function resolveThemeKey(roomId, explicitThemeKey) {
  if (explicitThemeKey && ROOM_THEME_SPECS[explicitThemeKey]) {
    return explicitThemeKey;
  }
  const base = roomId && roomId !== 'lobby' ? roomId : 'great_hall';
  return ROOM_THEME_ORDER[stableHash(base) % ROOM_THEME_ORDER.length];
}

export function getThemeSpec(roomId, explicitThemeKey) {
  const themeKey = resolveThemeKey(roomId, explicitThemeKey);
  return ROOM_THEME_SPECS[themeKey];
}

export { ROOM_THEME_ORDER, ROOM_THEME_SPECS };
