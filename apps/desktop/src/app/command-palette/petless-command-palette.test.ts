import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const COMMAND_PALETTE_SOURCE = readFileSync(join(process.cwd(), 'src/app/command-palette/index.tsx'), 'utf8')

describe('petless command palette source guards', () => {
  it('does not expose pet entries or nested pet pages', () => {
    expect(COMMAND_PALETTE_SOURCE).not.toMatch(
      /appearance-(?:pets|generate-pet)|PetPalettePage|PetInlineToggle|openPetGenerate|to:\s*['"]pets['"]|page\s*===\s*['"]pets['"]/
    )
  })
})
