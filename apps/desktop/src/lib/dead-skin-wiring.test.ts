import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

// Surviving files that used to wire the desktop's /skin theme-cycling command
// (retired: one NadicodeAI skin, not an operator choice).
const WIRING_FILES = [
  'src/app/desktop-controller.tsx',
  'src/app/session/hooks/use-prompt-actions/slash.ts',
  'src/app/session/hooks/use-prompt-actions/index.ts',
  'src/app/chat/composer/hooks/use-slash-completions.ts',
  'src/app/chat/composer/index.tsx'
]

describe('the desktop /skin theme-cycling command is fully retired', () => {
  it('deletes the use-skin-command module', () => {
    expect(existsSync(join(process.cwd(), 'src/themes/use-skin-command.ts'))).toBe(false)
  })

  it('no surviving module imports or wires the skin command handler', () => {
    for (const relPath of WIRING_FILES) {
      const source = readFileSync(join(process.cwd(), relPath), 'utf8')

      expect(source).not.toMatch(/use-skin-command|useSkinCommand|handleSkinCommand|skinThemes|activeSkin/)
    }
  })
})
