import type { Locale } from './types'

export const DEFAULT_LOCALE: Locale = 'en'

export const LOCALE_OPTIONS = [
  {
    id: 'en',
    name: 'English',
    englishName: 'English',
    configValue: 'en'
  },
  {
    id: 'it',
    name: 'Italiano',
    englishName: 'Italian',
    configValue: 'it'
  }
] as const satisfies readonly { configValue: string; englishName: string; id: Locale; name: string }[]

// `name` is the endonym (native name) shown in the picker so users recognize
// their language regardless of the current UI language. No country flags:
// languages are not countries. `englishName` is search-only (not shown) so an
// English speaker can type "italian" to filter the list.
export const LOCALE_META: Record<Locale, { name: string; englishName: string }> = Object.fromEntries(
  LOCALE_OPTIONS.map(locale => [locale.id, { name: locale.name, englishName: locale.englishName }])
) as Record<Locale, { name: string; englishName: string }>

const LOCALE_ALIASES: Record<string, Locale> = {
  en: 'en',
  'en-us': 'en',
  en_us: 'en',
  'en-gb': 'en',
  en_gb: 'en',
  english: 'en',
  it: 'it',
  'it-it': 'it',
  it_it: 'it',
  'it-ch': 'it',
  it_ch: 'it',
  italian: 'it',
  italiano: 'it'
}

function normalizeLocaleKey(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, '-').split('.', 1)[0]
}

export function supportedLocaleFromValue(value: unknown): Locale | null {
  if (typeof value !== 'string') {
    return null
  }

  const key = normalizeLocaleKey(value)

  if (!key) {
    return null
  }

  if (LOCALE_ALIASES[key]) {
    return LOCALE_ALIASES[key]
  }

  const base = key.split('-', 1)[0]
  return LOCALE_ALIASES[base] ?? null
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && LOCALE_OPTIONS.some(locale => locale.id === value)
}

export function normalizeLocale(value: unknown): Locale {
  return supportedLocaleFromValue(value) ?? DEFAULT_LOCALE
}

export function detectSystemLocale(): Locale {
  const candidates =
    typeof navigator === 'undefined' ? [] : [...(navigator.languages ?? []), navigator.language].filter(Boolean)

  return candidates.some(candidate => supportedLocaleFromValue(candidate) === 'it') ? 'it' : DEFAULT_LOCALE
}

export function isSupportedLocaleValue(value: unknown): boolean {
  return supportedLocaleFromValue(value) != null
}

export function localeConfigValue(locale: Locale): string {
  return LOCALE_OPTIONS.find(item => item.id === locale)?.configValue ?? DEFAULT_LOCALE
}
