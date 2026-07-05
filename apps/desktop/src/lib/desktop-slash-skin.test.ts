import { describe, expect, it } from 'vitest'

import { isDesktopSlashCommand, isDesktopSlashSuggestion } from './desktop-slash-commands'

// Skin slash commands are gone from the desktop: `/skin` is neither suggested
// in the composer palette nor executable as a desktop command.
describe('/skin is gone from the desktop', () => {
  it('is not suggested in the slash palette', () => {
    expect(isDesktopSlashSuggestion('/skin')).toBe(false)
  })

  it('does not execute as a desktop command', () => {
    expect(isDesktopSlashCommand('/skin')).toBe(false)
  })
})
