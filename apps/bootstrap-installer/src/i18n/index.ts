/*
 * Installer i18n entry point.
 *
 * The installer follows the OS language and never switches at runtime (no
 * picker), so the active catalog is resolved once from
 * detectLocale() and shared through a tiny context. `I18nProvider` takes an
 * optional `locale` override used only by tests to pin a locale; production
 * wraps the app with no locale and lets the OS decide.
 */
import { createContext, createElement, useContext, type ReactNode } from 'react'

import { detectLocale, DEFAULT_LOCALE } from './detect'
import { en } from './en'
import { it } from './it'
import type { Catalog, Locale } from './types'

export const messages: Record<Locale, Catalog> = { en, it }

const I18nContext = createContext<Catalog>(messages[DEFAULT_LOCALE])

export function I18nProvider({ locale, children }: { locale?: Locale; children: ReactNode }) {
  const active = locale ?? detectLocale()
  return createElement(I18nContext.Provider, { value: messages[active] }, children)
}

export function useI18n(): Catalog {
  return useContext(I18nContext)
}

export type { Catalog, Locale } from './types'
export { detectLocale, DEFAULT_LOCALE } from './detect'
