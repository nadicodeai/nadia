import { describe, expect, it as test } from 'vitest'

import { en } from './en'
import { it } from './it'
import type { Translations } from './types'

// Collect every leaf key path in a translations tree. Function and array
// leaves count as present (their key path is what matters for completeness);
// we do not recurse into them.
function leafPaths(node: unknown, prefix = ''): string[] {
  if (node === null || typeof node !== 'object' || Array.isArray(node) || typeof node === 'function') {
    return [prefix]
  }

  return Object.entries(node as Record<string, unknown>).flatMap(([key, value]) =>
    leafPaths(value, prefix ? `${prefix}.${key}` : key)
  )
}

describe('Italian desktop catalog', () => {
  test('covers all 33 top-level translation sections', () => {
    const sections = Object.keys(en) as (keyof Translations)[]

    expect(sections).toHaveLength(33)

    for (const section of sections) {
      expect(it, `missing section: ${String(section)}`).toHaveProperty(section)
    }
  })

  test('has the same key structure as English — no missing keys', () => {
    const enPaths = leafPaths(en).sort()
    const itPaths = leafPaths(it).sort()

    const missingInIt = enPaths.filter(path => !itPaths.includes(path))
    const extraInIt = itPaths.filter(path => !enPaths.includes(path))

    expect(missingInIt, `keys missing from Italian: ${missingInIt.join(', ')}`).toEqual([])
    expect(extraInIt, `keys only in Italian: ${extraInIt.join(', ')}`).toEqual([])
  })

  test('renders the signed desktop settings samples in Italian', () => {
    // italian.feature: the Settings save/apply controls.
    expect(it.common.save).toBe('Salva')
    expect(it.common.apply).toBe('Applica')
  })

  test('translates the settings chrome away from English', () => {
    expect(it.settings.sections.appearance).not.toBe(en.settings.sections.appearance)
    expect(it.settings.nav.about).not.toBe(en.settings.nav.about)
    expect(it.onboarding.startChatting).not.toBe(en.onboarding.startChatting)
    expect(it.language.label).toBe('Lingua')
  })
})

// Config-field labels and descriptions (Settings → every section) must render
// in Italian under Italiano. Values legitimately identical across both
// languages (proper nouns / codes with no Italian form) go on the explicit
// allowlist; everything else is a leak.
const INVARIANT_FIELD_COPY = new Set<string>([])

describe('Italian settings field copy', () => {
  test('every config-field label is translated to Italian', () => {
    const leaked = Object.keys(en.settings.fieldLabels).filter(
      key =>
        !INVARIANT_FIELD_COPY.has(en.settings.fieldLabels[key]) &&
        it.settings.fieldLabels[key] === en.settings.fieldLabels[key]
    )

    expect(leaked, `English field labels under Italiano: ${leaked.join(', ')}`).toEqual([])
  })

  test('every config-field description is translated to Italian', () => {
    const leaked = Object.keys(en.settings.fieldDescriptions).filter(
      key =>
        !INVARIANT_FIELD_COPY.has(en.settings.fieldDescriptions[key]) &&
        it.settings.fieldDescriptions[key] === en.settings.fieldDescriptions[key]
    )

    expect(leaked, `English field descriptions under Italiano: ${leaked.join(', ')}`).toEqual([])
  })
})
