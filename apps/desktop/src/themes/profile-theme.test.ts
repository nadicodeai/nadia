import { beforeEach, describe, expect, it } from 'vitest'

import { modePref, type ThemeMode } from './context'

// One NadicodeAI skin: mode is the only per-profile appearance value (there is
// no per-profile skin map anymore). "default" is the legacy global slot; named
// profiles fall back to it until assigned.
describe('per-profile mode', () => {
  beforeEach(() => window.localStorage.clear())

  it('falls back to system when unassigned', () => {
    expect(modePref.resolve('default')).toBe('system')
    expect(modePref.resolve('work')).toBe('system')
  })

  it('keeps each profile on its own mode', () => {
    modePref.assign('work', 'dark')
    modePref.assign('default', 'light')
    expect(modePref.resolve('work')).toBe('dark')
    expect(modePref.resolve('default')).toBe('light')
  })

  it('lets unassigned profiles inherit the default profile as the global fallback', () => {
    modePref.assign('default', 'dark')
    expect(modePref.resolve('never-themed')).toBe('dark')
  })

  it('normalizes an unknown stored mode back to system', () => {
    modePref.assign('work', 'dusk' as ThemeMode)
    expect(modePref.resolve('work')).toBe('system')
  })
})
