/*
 * OS-language detection for the installer (follow the OS, no
 * picker). This is the house precedent from the desktop app
 * (apps/desktop/src/i18n/languages.ts detectSystemLocale): read the webview's
 * navigator language list — the only OS-locale signal the Tauri webview
 * exposes without an extra plugin — and pick Italian when any candidate is
 * Italian, English otherwise.
 */
import type { Locale } from './types'

export const DEFAULT_LOCALE: Locale = 'en'

function isItalianTag(tag: string): boolean {
  return tag.trim().toLowerCase().replace(/_/g, '-').split(/[-.]/, 1)[0] === 'it'
}

function navigatorCandidates(): string[] {
  if (typeof navigator === 'undefined') {
    return []
  }
  return [...(navigator.languages ?? []), navigator.language].filter(Boolean) as string[]
}

export function detectLocale(candidates: readonly string[] = navigatorCandidates()): Locale {
  return candidates.some(isItalianTag) ? 'it' : DEFAULT_LOCALE
}
