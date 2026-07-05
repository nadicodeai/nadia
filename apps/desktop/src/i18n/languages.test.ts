import { describe, expect, it } from 'vitest'

import {
  DEFAULT_LOCALE,
  detectSystemLocale,
  isLocale,
  isSupportedLocaleValue,
  localeConfigValue,
  LOCALE_OPTIONS,
  normalizeLocale
} from './languages'

describe('desktop i18n languages', () => {
  it('offers exactly two languages: English and Italiano', () => {
    expect(LOCALE_OPTIONS.map(option => option.id)).toEqual(['en', 'it'])
    expect(LOCALE_OPTIONS.map(option => option.name)).toEqual(['English', 'Italiano'])
  })

  it('normalizes supported locale aliases', () => {
    expect(normalizeLocale('en')).toBe('en')
    expect(normalizeLocale('EN-US')).toBe('en')
    expect(normalizeLocale('it')).toBe('it')
    expect(normalizeLocale('IT-IT')).toBe('it')
    expect(normalizeLocale(' it_it ')).toBe('it')
  })

  it('falls back to English for empty, unsupported, or retired locale values', () => {
    expect(normalizeLocale(null)).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('')).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('de')).toBe(DEFAULT_LOCALE)
    // Locales that used to ship but were retired resolve to English, not a crash.
    expect(normalizeLocale('zh')).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('zh-Hant')).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('ja')).toBe(DEFAULT_LOCALE)
  })

  it('distinguishes exact locale ids from supported config aliases', () => {
    expect(isSupportedLocaleValue('it-IT')).toBe(true)
    expect(isSupportedLocaleValue('en-US')).toBe(true)
    expect(isSupportedLocaleValue('ja-JP')).toBe(false)
    expect(isSupportedLocaleValue('de')).toBe(false)
    expect(isLocale('it-IT')).toBe(false)
    expect(isLocale('it')).toBe(true)
    expect(isLocale('en')).toBe(true)
    expect(isLocale('ja')).toBe(false)
  })

  it('returns the persisted config value for supported locales', () => {
    expect(localeConfigValue('en')).toBe('en')
    expect(localeConfigValue('it')).toBe('it')
  })

  it('detects an Italian system as Italian on first run', () => {
    const original = Object.getOwnPropertyDescriptor(globalThis, 'navigator')

    try {
      Object.defineProperty(globalThis, 'navigator', {
        configurable: true,
        value: { languages: ['it-IT', 'en-US'], language: 'it-IT' }
      })

      expect(detectSystemLocale()).toBe('it')
    } finally {
      if (original) {
        Object.defineProperty(globalThis, 'navigator', original)
      }
    }
  })

  it('detects a non-Italian system as English', () => {
    const original = Object.getOwnPropertyDescriptor(globalThis, 'navigator')

    try {
      Object.defineProperty(globalThis, 'navigator', {
        configurable: true,
        value: { languages: ['en-US'], language: 'en-US' }
      })

      expect(detectSystemLocale()).toBe(DEFAULT_LOCALE)
    } finally {
      if (original) {
        Object.defineProperty(globalThis, 'navigator', original)
      }
    }
  })
})
