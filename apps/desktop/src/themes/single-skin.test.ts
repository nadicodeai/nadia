import { describe, expect, it } from 'vitest'

import { BUILTIN_THEME_LIST, BUILTIN_THEMES, DEFAULT_SKIN_NAME } from './presets'

// One NadicodeAI skin on every surface: the desktop ships exactly the `nous`
// identity. Light/dark/system modes render it; there is no second skin.
describe('one NadicodeAI skin', () => {
  it('ships exactly the nadia skin', () => {
    expect(Object.keys(BUILTIN_THEMES)).toEqual(['nadia'])
    expect(BUILTIN_THEME_LIST).toHaveLength(1)
    expect(BUILTIN_THEME_LIST[0]?.name).toBe('nadia')
  })

  it('defaults to the nadia skin', () => {
    expect(DEFAULT_SKIN_NAME).toBe('nadia')
    expect(BUILTIN_THEMES[DEFAULT_SKIN_NAME]).toBeDefined()
  })

  it('keeps both light and dark palettes for the one skin', () => {
    expect(BUILTIN_THEMES.nous?.colors.background).toBeTruthy()
    expect(BUILTIN_THEMES.nous?.darkColors?.background).toBeTruthy()
  })
})
