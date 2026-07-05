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
// The NadicodeAI brand green — design-system `color.primary` token. Kept
// identical in light and dark (DESIGN.md pins this token the same way it
// pins `chart-2`) so the accent reads as the same green in both modes.
const NADIA_PRIMARY = '#008c45'
const NADIA_LINK = '#007a3c'
const NADIA_LINK_DEEP = '#00602f'
const NADIA_LINK_BG_SOFT = '#d9f6e4'
const NADIA_ERROR = '#b80022'
const NADIA_CYAN = '#50e3c2'
const NADIA_DARK_CANVAS = '#0a0a0a'
const NADIA_DARK_CANVAS_SOFT = '#171717'
const NADIA_DARK_CANVAS_SOFT_2 = '#262626'
const NADIA_DARK_INK = '#f5f5f5'
const NADIA_DARK_BODY = '#d4d4d4'
const NADIA_DARK_MUTED = '#a3a3a3'
const NADIA_DARK_LINE = '#2e2e2e'
const NADIA_DARK_SEAM = '#1f1f1f'
const NADIA_DARK_LINK = '#9fe6bc'
const NADIA_DARK_LINK_BG_SOFT = '#00301a'
const NADIA_DARK_ERROR = '#f7b3b5'
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
    primary: NADIA_PRIMARY,
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
    primary: NADIA_PRIMARY,
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

// One NadicodeAI skin: light/dark/system modes render the single `nous`
// identity. Nadia is not a skin gallery — the upstream preset themes
// (midnight/ember/mono/cyberpunk/slate) are retired.
export const BUILTIN_THEMES: Record<string, DesktopTheme> = {
  nadia: nadiaTheme
}

export const BUILTIN_THEME_LIST = Object.values(BUILTIN_THEMES)

/** Skin used when nothing is persisted or the persisted name is retired. */
export const DEFAULT_SKIN_NAME = 'nadia'
