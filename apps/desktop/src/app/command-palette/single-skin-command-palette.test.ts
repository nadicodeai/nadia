import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const SRC = readFileSync(join(process.cwd(), 'src/app/command-palette/index.tsx'), 'utf8')

// One skin: the command palette exposes no skin/theme gallery, no VS Code
// Marketplace theme browser, and does not reach into the user-theme registry.
describe('command palette has no skin gallery', () => {
  it('offers no theme gallery entry or marketplace theme page', () => {
    expect(SRC).not.toMatch(/id:\s*['"]appearance-theme['"]|MarketplaceThemePage|to:\s*['"]theme['"]|to:\s*['"]install-theme['"]/)
  })

  it('does not depend on the deleted user-theme machinery', () => {
    expect(SRC).not.toMatch(/themes\/user-themes|marketplace-theme-page|themeSupportsMode/)
  })
})
