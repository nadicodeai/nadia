import { describe, expect, it as test } from 'vitest'

import { messages } from './index'

/**
 * Structural parity: `it` must mirror `en` key-for-key (including the stage
 * map and which entries are interpolation functions). The Catalog type already
 * makes a missing key a compile error; this guards the runtime shape too, so a
 * dropped or retyped entry fails loudly.
 */
function shape(value: unknown): unknown {
  if (typeof value === 'function') {
    return 'fn'
  }
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      out[key] = shape((value as Record<string, unknown>)[key])
    }
    return out
  }
  return typeof value
}

describe('installer i18n catalogs', () => {
  test('exposes exactly English and Italian', () => {
    expect(Object.keys(messages).sort()).toEqual(['en', 'it'])
  })

  test('it mirrors en structurally', () => {
    expect(shape(messages.it)).toEqual(shape(messages.en))
  })

  test('every route section is present in both locales', () => {
    for (const locale of ['en', 'it'] as const) {
      const c = messages[locale]
      expect(Object.keys(c).sort()).toEqual([
        'causes',
        'errorDetailLabel',
        'failure',
        'progress',
        'stages',
        'success',
        'welcome'
      ])
    }
  })

  test('English and Italian differ where it matters (not accidental copies)', () => {
    expect(messages.it.welcome.installCta).not.toBe(messages.en.welcome.installCta)
    expect(messages.it.failure.openLogs).not.toBe(messages.en.failure.openLogs)
    expect(messages.it.progress.cancel).toBe('Annulla')
  })

  test('line count pluralizes: 1 riga / n righe (en: 1 line / n lines)', () => {
    expect(messages.it.progress.lineCount(1)).toBe('1 riga')
    expect(messages.it.progress.lineCount(0)).toBe('0 righe')
    expect(messages.it.progress.lineCount(2)).toBe('2 righe')
    expect(messages.en.progress.lineCount(1)).toBe('1 line')
    expect(messages.en.progress.lineCount(2)).toBe('2 lines')
  })

  test('Italian stage labels stay terse so the truncated stage row survives at 720px', () => {
    // The stage list narrows to half-width with the log panel open; long labels
    // clip mid-word. Terse register is the house style — keep each under budget.
    const BUDGET = 30
    for (const [name, label] of Object.entries(messages.it.stages)) {
      expect(label.length, `it.stages.${name} = "${label}" (${label.length})`).toBeLessThanOrEqual(
        BUDGET
      )
    }
  })

  test('every known failure cause has a non-empty message in both locales', () => {
    const causes = [
      'alreadyRunning',
      'notInstalled',
      'rebuild',
      'desktopMissing',
      'download',
      'disk',
      'permission',
      'cancelled'
    ] as const
    for (const locale of ['en', 'it'] as const) {
      for (const cause of causes) {
        expect(messages[locale].causes[cause].length).toBeGreaterThan(0)
      }
    }
  })
})
