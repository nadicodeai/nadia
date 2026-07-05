import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const SRC = readFileSync(join(process.cwd(), 'src/components/language-switcher.tsx'), 'utf8')

// Changing the language is a silent setting: switching locale plays no haptic
// click.
describe('language switcher — silent', () => {
  it('plays no haptic when the locale changes', () => {
    expect(SRC).not.toMatch(/triggerHaptic/)
  })
})
