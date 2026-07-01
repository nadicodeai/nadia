/**
 * Built-in desktop themes. Names match the CLI skins / dashboard presets.
 * Add new themes here — no code changes needed elsewhere.
 */

import type { DesktopTheme, DesktopThemeTypography } from './types'

// Color-emoji fonts to append to every stack as a last resort. None of the UI
// text/mono fonts carry emoji glyphs, so without this emoji render as tofu
// boxes on platforms whose default text font lacks them (e.g. Linux/#40364).
// Covers macOS, Windows, Linux, plus the `emoji` generic for anything else.
export const EMOJI_FALLBACK = '"Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji", emoji'

const SYSTEM_SANS =
  '"Geist", "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Segoe WPC", sans-serif, ' +
  EMOJI_FALLBACK

const SYSTEM_MONO =
  '"Geist Mono", "JetBrains Mono", "Cascadia Code", "SF Mono", ui-monospace, Menlo, Monaco, Consolas, monospace, ' + EMOJI_FALLBACK

export const DEFAULT_TYPOGRAPHY: DesktopThemeTypography = { fontSans: SYSTEM_SANS, fontMono: SYSTEM_MONO }

const NADIA_INK = '#171717'
const NADIA_BODY = '#4d4d4d'
const NADIA_MUTED = '#888888'
const NADIA_CANVAS = '#ffffff'
const NADIA_CANVAS_SOFT = '#fafafa'
const NADIA_CANVAS_SOFT_2 = '#f5f5f5'
const NADIA_LINE = '#e5e5e5'
const NADIA_SEAM = '#e4e7ec'
const NADIA_LINK = '#007a5e'
const NADIA_LINK_DEEP = '#005d49'
const NADIA_LINK_BG_SOFT = '#d8f0e9'
const NADIA_ERROR = '#b80022'
const NADIA_CYAN = '#50e3c2'
const NADIA_DARK_CANVAS = '#101414'
const NADIA_DARK_CANVAS_SOFT = '#151b19'
const NADIA_DARK_CANVAS_SOFT_2 = '#1d2522'
const NADIA_DARK_INK = '#f5f7f4'
const NADIA_DARK_BODY = '#c8d0cb'
const NADIA_DARK_MUTED = '#8d9892'
const NADIA_DARK_LINE = '#2c3632'
const NADIA_DARK_SEAM = '#24302b'
const NADIA_DARK_LINK = '#7ee7c6'
const NADIA_DARK_LINK_BG_SOFT = '#163f34'
const NADIA_DARK_ERROR = '#ff7a8b'
const NADIA_DARK_CYAN = '#83f7dc'

/**
 * Nadia — canonical NadicodeAI desktop identity. Values mirror the public
 * @nadicodeai/design-system CSS token export so the desktop default follows
 * the same brand surface as the web and docs.
 */
export const nadiaTheme: DesktopTheme = {
  name: 'nadia',
  label: 'Nadia',
  description: 'NadicodeAI design-system palette with green/cyan accents',
  colors: {
    background: NADIA_CANVAS,
    foreground: NADIA_INK,
    card: NADIA_CANVAS,
    cardForeground: NADIA_INK,
    muted: NADIA_CANVAS_SOFT_2,
    mutedForeground: NADIA_MUTED,
    popover: NADIA_CANVAS,
    popoverForeground: NADIA_INK,
    primary: NADIA_LINK,
    primaryForeground: NADIA_CANVAS,
    secondary: NADIA_CANVAS_SOFT,
    secondaryForeground: NADIA_BODY,
    accent: NADIA_LINK_BG_SOFT,
    accentForeground: NADIA_LINK_DEEP,
    border: NADIA_LINE,
    input: NADIA_SEAM,
    ring: NADIA_LINK,
    midground: NADIA_CYAN,
    composerRing: NADIA_LINK,
    destructive: NADIA_ERROR,
    destructiveForeground: NADIA_CANVAS,
    sidebarBackground: NADIA_CANVAS_SOFT,
    sidebarBorder: NADIA_SEAM,
    userBubble: NADIA_LINK_BG_SOFT,
    userBubbleBorder: NADIA_SEAM
  },
  darkColors: {
    background: NADIA_DARK_CANVAS,
    foreground: NADIA_DARK_INK,
    card: NADIA_DARK_CANVAS_SOFT,
    cardForeground: NADIA_DARK_INK,
    muted: NADIA_DARK_CANVAS_SOFT_2,
    mutedForeground: NADIA_DARK_MUTED,
    popover: NADIA_DARK_CANVAS_SOFT,
    popoverForeground: NADIA_DARK_INK,
    primary: NADIA_DARK_LINK,
    primaryForeground: NADIA_DARK_CANVAS,
    secondary: NADIA_DARK_CANVAS_SOFT_2,
    secondaryForeground: NADIA_DARK_BODY,
    accent: NADIA_DARK_LINK_BG_SOFT,
    accentForeground: NADIA_DARK_LINK,
    border: NADIA_DARK_LINE,
    input: NADIA_DARK_SEAM,
    ring: NADIA_DARK_LINK,
    midground: NADIA_DARK_CYAN,
    composerRing: NADIA_DARK_LINK,
    destructive: NADIA_DARK_ERROR,
    destructiveForeground: NADIA_DARK_CANVAS,
    sidebarBackground: NADIA_DARK_CANVAS,
    sidebarBorder: NADIA_DARK_SEAM,
    userBubble: NADIA_DARK_LINK_BG_SOFT,
    userBubbleBorder: NADIA_DARK_SEAM
  },
  typography: {
    fontSans: SYSTEM_SANS,
    fontMono: SYSTEM_MONO
  }
}

/** Deep blue-violet with cool accents. Matches the dashboard midnight theme. */
export const midnightTheme: DesktopTheme = {
  name: 'midnight',
  label: 'Midnight',
  description: 'Deep blue-violet with cool accents',
  colors: {
    background: '#08081c',
    foreground: '#ddd6ff',
    card: '#0d0d28',
    cardForeground: '#ddd6ff',
    muted: '#13133a',
    mutedForeground: '#7c7ab0',
    popover: '#0f0f2e',
    popoverForeground: '#ddd6ff',
    primary: '#ddd6ff',
    primaryForeground: '#08081c',
    secondary: '#1a1a4a',
    secondaryForeground: '#c4bff0',
    accent: '#1a1a44',
    accentForeground: '#d0c8ff',
    border: '#1e1e52',
    input: '#1e1e52',
    ring: '#8b80e8',
    midground: '#8b80e8',
    destructive: '#b03060',
    destructiveForeground: '#fef2f2',
    sidebarBackground: '#06061a',
    sidebarBorder: '#12123a',
    userBubble: '#14143a',
    userBubbleBorder: '#242466'
  },
  typography: {
    fontMono: `"JetBrains Mono", ${SYSTEM_MONO}`,
    fontUrl: 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap'
  }
}

/** Warm crimson and bronze — forge vibes. Matches the CLI ares skin. */
export const emberTheme: DesktopTheme = {
  name: 'ember',
  label: 'Ember',
  description: 'Warm crimson and bronze — forge vibes',
  colors: {
    background: '#160800',
    foreground: '#ffd8b0',
    card: '#1e0e04',
    cardForeground: '#ffd8b0',
    muted: '#2a1408',
    mutedForeground: '#aa7a56',
    popover: '#221008',
    popoverForeground: '#ffd8b0',
    primary: '#ffd8b0',
    primaryForeground: '#160800',
    secondary: '#341800',
    secondaryForeground: '#f0c090',
    accent: '#301600',
    accentForeground: '#e8c080',
    border: '#3a1c08',
    input: '#3a1c08',
    ring: '#d97316',
    midground: '#d97316',
    destructive: '#c43010',
    destructiveForeground: '#fef2f2',
    sidebarBackground: '#100600',
    sidebarBorder: '#2a1004',
    userBubble: '#2a1000',
    userBubbleBorder: '#4a2010'
  },
  typography: {
    fontMono: `"IBM Plex Mono", ${SYSTEM_MONO}`,
    fontUrl: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&display=swap'
  }
}

/** Clean grayscale. Matches the CLI mono skin and dashboard mono theme. */
export const monoTheme: DesktopTheme = {
  name: 'mono',
  label: 'Mono',
  description: 'Clean grayscale — minimal and focused',
  colors: {
    background: '#0e0e0e',
    foreground: '#eaeaea',
    card: '#141414',
    cardForeground: '#eaeaea',
    muted: '#1e1e1e',
    mutedForeground: '#808080',
    popover: '#181818',
    popoverForeground: '#eaeaea',
    primary: '#eaeaea',
    primaryForeground: '#0e0e0e',
    secondary: '#262626',
    secondaryForeground: '#c8c8c8',
    accent: '#222222',
    accentForeground: '#d8d8d8',
    border: '#2a2a2a',
    input: '#2a2a2a',
    ring: '#9a9a9a',
    midground: '#9a9a9a',
    destructive: '#a84040',
    destructiveForeground: '#fef2f2',
    sidebarBackground: '#0a0a0a',
    sidebarBorder: '#202020',
    userBubble: '#1a1a1a',
    userBubbleBorder: '#363636'
  }
}

/** Neon green on black. Matches the CLI cyberpunk skin and dashboard theme. */
export const cyberpunkTheme: DesktopTheme = {
  name: 'cyberpunk',
  label: 'Cyberpunk',
  description: 'Neon green on black — matrix terminal',
  colors: {
    background: '#000a00',
    foreground: '#00ff41',
    card: '#001200',
    cardForeground: '#00ff41',
    muted: '#001a00',
    mutedForeground: '#1a8a30',
    popover: '#001000',
    popoverForeground: '#00ff41',
    primary: '#00ff41',
    primaryForeground: '#000a00',
    secondary: '#002800',
    secondaryForeground: '#00cc34',
    accent: '#002000',
    accentForeground: '#00e038',
    border: '#003000',
    input: '#003000',
    ring: '#00ff41',
    midground: '#00ff41',
    destructive: '#ff003c',
    destructiveForeground: '#000a00',
    sidebarBackground: '#000600',
    sidebarBorder: '#001800',
    userBubble: '#001400',
    userBubbleBorder: '#004800'
  },
  typography: {
    fontMono: `"Courier New", Courier, monospace, ${EMOJI_FALLBACK}`,
    fontSans: `"Courier New", Courier, monospace, ${EMOJI_FALLBACK}`
  }
}

/** Cool slate blue for developers. Matches the CLI slate skin. */
export const slateTheme: DesktopTheme = {
  name: 'slate',
  label: 'Slate',
  description: 'Cool slate blue — focused developer theme',
  colors: {
    background: '#0d1117',
    foreground: '#c9d1d9',
    card: '#161b22',
    cardForeground: '#c9d1d9',
    muted: '#21262d',
    mutedForeground: '#8b949e',
    popover: '#1c2128',
    popoverForeground: '#c9d1d9',
    primary: '#c9d1d9',
    primaryForeground: '#0d1117',
    secondary: '#2a3038',
    secondaryForeground: '#adb5bf',
    accent: '#1e2530',
    accentForeground: '#c0c8d0',
    border: '#30363d',
    input: '#30363d',
    ring: '#58a6ff',
    midground: '#58a6ff',
    destructive: '#cf4848',
    destructiveForeground: '#fef2f2',
    sidebarBackground: '#090d13',
    sidebarBorder: '#1c2228',
    userBubble: '#1e2a38',
    userBubbleBorder: '#2e4060'
  },
  typography: {
    fontMono: `"JetBrains Mono", ${SYSTEM_MONO}`
  }
}

export const BUILTIN_THEMES: Record<string, DesktopTheme> = {
  nadia: nadiaTheme,
  midnight: midnightTheme,
  ember: emberTheme,
  mono: monoTheme,
  cyberpunk: cyberpunkTheme,
  slate: slateTheme
}

export const BUILTIN_THEME_LIST = Object.values(BUILTIN_THEMES)

/** Skin used when nothing is persisted or the persisted name is retired. */
export const DEFAULT_SKIN_NAME = 'nadia'
