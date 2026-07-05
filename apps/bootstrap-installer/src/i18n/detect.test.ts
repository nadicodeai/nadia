import { describe, expect, it as test } from 'vitest'

import { detectLocale } from './detect'

describe('installer detectLocale (OS-language follow, no picker)', () => {
  test('picks Italian when any candidate is Italian', () => {
    expect(detectLocale(['it'])).toBe('it')
    expect(detectLocale(['it-IT'])).toBe('it')
    expect(detectLocale(['IT_it'])).toBe('it')
    expect(detectLocale(['it-IT', 'en-US'])).toBe('it')
    expect(detectLocale(['en-US', 'it'])).toBe('it')
  })

  test('falls back to English for non-Italian or empty candidates', () => {
    expect(detectLocale(['en-US'])).toBe('en')
    expect(detectLocale(['de-DE'])).toBe('en')
    expect(detectLocale(['fr', 'es'])).toBe('en')
    expect(detectLocale([])).toBe('en')
  })

  test('does not treat a non-Italian tag that merely contains "it" as Italian', () => {
    expect(detectLocale(['lit'])).toBe('en')
    expect(detectLocale(['en-GB'])).toBe('en')
  })
})
