import { getUiState } from '../app/uiStore.js'

import { en } from './en.js'
import { it } from './it.js'
import type { Catalog, CatalogKey, Locale } from './types.js'

export { en } from './en.js'
export { it } from './it.js'
export type { Catalog, CatalogKey, Locale } from './types.js'

export const catalogs: Record<Locale, Catalog> = { en, it }

const SUPPORTED_LOCALES = Object.keys(catalogs) as Locale[]

export const resolveLocale = (raw: unknown): Locale => {
  if (typeof raw !== 'string') {
    return 'en'
  }

  const key = raw.trim().toLowerCase().replace(/_/g, '-').split('.', 1)[0]

  if (!key) {
    return 'en'
  }

  if ((SUPPORTED_LOCALES as string[]).includes(key)) {
    return key as Locale
  }

  const base = key.split('-', 1)[0]

  return (SUPPORTED_LOCALES as string[]).includes(base) ? (base as Locale) : 'en'
}

const readCatalogString = (catalog: Catalog, key: CatalogKey): string => {
  const value = key.split('.').reduce<unknown>((current, part) => {
    if (current && typeof current === 'object' && part in current) {
      return (current as Record<string, unknown>)[part]
    }

    return undefined
  }, catalog)

  return typeof value === 'string' ? value : ''
}

export const t = (key: CatalogKey): string => {
  const locale = resolveLocale(getUiState().locale)
  const catalog = catalogs[locale] ?? en

  return readCatalogString(catalog, key)
}
