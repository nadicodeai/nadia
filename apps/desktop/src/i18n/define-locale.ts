import { en } from './en'
import type { Translations } from './types'

type TranslationOverride<T> = T extends (...args: never[]) => string
  ? T
  : T extends readonly unknown[]
    ? T
    : T extends string
      ? string
      : T extends object
        ? { [K in keyof T]?: TranslationOverride<T[K]> }
        : T

export type TranslationOverrides = TranslationOverride<Translations>

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mergeTranslations<T>(base: T, overrides: TranslationOverride<T> | undefined): T {
  if (!isRecord(base) || !isRecord(overrides)) {
    return (overrides ?? base) as T
  }

  const result: Record<string, unknown> = { ...base }

  for (const [key, value] of Object.entries(overrides)) {
    if (value === undefined) {
      continue
    }

    const baseValue = result[key]
    result[key] = isRecord(baseValue) && isRecord(value) ? mergeTranslations(baseValue, value) : value
  }

  return result as T
}

// a locale passed here must be a complete `Translations`: a
// missing key is a compile error, not a silent English fallback. The English
// merge stays as a runtime backstop for the loosely-typed field-copy records.
export function defineLocale(translations: Translations): Translations {
  return mergeTranslations<Translations>(en, translations)
}
