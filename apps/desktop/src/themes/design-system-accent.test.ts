import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

import { BUILTIN_THEMES } from './presets'

// Reads the design-system token AT TEST TIME from the installed package
// (never a hardcoded copy of the hex) so future drift between the desktop
// theme and the @nadicodeai/design-system contract fails this test instead
// of silently diverging — the #007a5e/#7ee7c6 regression this guards against
// was exactly a hand-mirrored constant going stale.
const require = createRequire(import.meta.url)
const dtcgPath = require.resolve('@nadicodeai/design-system/tokens/dtcg')
const designSystemTokens = JSON.parse(readFileSync(dtcgPath, 'utf8')) as {
  nadicode: { color: Record<string, { $value: { hex: string } }> }
}
const DESIGN_SYSTEM_PRIMARY_GREEN = designSystemTokens.nadicode.color.primary.$value.hex

describe('nadia theme primary accent matches the design-system token (single-skin.feature)', () => {
  it('uses the NadicodeAI green as the primary accent in light mode', () => {
    expect(BUILTIN_THEMES.nous?.colors.primary).toBe(DESIGN_SYSTEM_PRIMARY_GREEN)
  })

  it('uses the NadicodeAI green as the primary accent in dark mode', () => {
    expect(BUILTIN_THEMES.nous?.darkColors?.primary).toBe(DESIGN_SYSTEM_PRIMARY_GREEN)
  })
})
