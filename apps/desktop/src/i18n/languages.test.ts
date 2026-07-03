import { describe, expect, it } from 'vitest'

import {
  DEFAULT_LOCALE,
  detectSystemLocale,
  isLocale,
  isSupportedLocaleValue,
  localeConfigValue,
  normalizeLocale
} from './languages'

describe('desktop i18n languages', () => {
  it('normalizes supported locale aliases', () => {
    expect(normalizeLocale('en')).toBe('en')
    expect(normalizeLocale('EN-US')).toBe('en')
    expect(normalizeLocale('it')).toBe('it')
    expect(normalizeLocale('it-IT')).toBe('it')
    expect(normalizeLocale(' italiano ')).toBe('it')
  })

  it('falls back to English for empty or unsupported values', () => {
    expect(normalizeLocale(null)).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('')).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('de')).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('zh-CN')).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('zh-TW')).toBe(DEFAULT_LOCALE)
    expect(normalizeLocale('ja-JP')).toBe(DEFAULT_LOCALE)
  })

  it('distinguishes exact locale ids from supported config aliases', () => {
    expect(isSupportedLocaleValue('it-IT')).toBe(true)
    expect(isSupportedLocaleValue('italiano')).toBe(true)
    expect(isSupportedLocaleValue('zh-CN')).toBe(false)
    expect(isSupportedLocaleValue('zh-TW')).toBe(false)
    expect(isSupportedLocaleValue('ja-JP')).toBe(false)
    expect(isSupportedLocaleValue('de')).toBe(false)
    expect(isLocale('it-IT')).toBe(false)
    expect(isLocale('it')).toBe(true)
  })

  it('returns the persisted config value for supported locales', () => {
    expect(localeConfigValue('en')).toBe('en')
    expect(localeConfigValue('it')).toBe('it')
  })

  it('detects Italian from browser/system locale metadata', () => {
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: {}
    })
    Object.defineProperty(globalThis.navigator, 'languages', {
      configurable: true,
      value: ['it-IT', 'en-US']
    })
    Object.defineProperty(globalThis.navigator, 'language', {
      configurable: true,
      value: 'it-IT'
    })

    expect(detectSystemLocale()).toBe('it')
  })
})
