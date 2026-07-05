import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const STYLES = readFileSync(join(process.cwd(), 'src/styles.css'), 'utf8')

// A business agent: no pet anywhere. The dead pet styling block carries no
// live selectors.
describe('styles.css has no pet styling', () => {
  it('defines no .pet- selectors', () => {
    expect(STYLES).not.toMatch(/\.pet-/)
  })
})
