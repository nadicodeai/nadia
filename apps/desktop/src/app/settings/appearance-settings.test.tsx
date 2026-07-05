import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// One NadicodeAI skin: the rendered Appearance section offers no skin, template,
// or theme gallery, no theme search box, no VS Code Marketplace import — and the
// appearance mode control (light/dark/system) is the single visual choice.
// Silent settings: changing the mode plays no haptic click.

const triggerHaptic = vi.fn()

vi.mock('@/lib/haptics', () => ({
  triggerHaptic: (intent?: string) => triggerHaptic(intent)
}))

const setMode = vi.fn()

vi.mock('@/themes/context', () => ({
  useTheme: () => ({
    theme: { name: 'nadia-light', label: 'Nadia Light', description: '', colors: {} },
    themeName: 'nous',
    mode: 'system',
    resolvedMode: 'light',
    renderedMode: 'light',
    availableThemes: [{ name: 'nous', label: 'Nadia', description: 'NadicodeAI design system' }],
    setTheme: () => {},
    setMode: (next: string) => setMode(next)
  })
}))

import { AppearanceSettings } from './appearance-settings'

afterEach(() => {
  cleanup()
  triggerHaptic.mockClear()
  setMode.mockClear()
})

describe('appearance settings — one skin, silent options', () => {
  it('shows the mode control and no theme gallery, search box, or marketplace import', () => {
    render(<AppearanceSettings />)

    // The appearance mode control is present, offering light, dark, and system.
    expect(screen.getByRole('button', { name: 'Light' })).toBeDefined()
    expect(screen.getByRole('button', { name: 'Dark' })).toBeDefined()
    expect(screen.getByRole('button', { name: 'System' })).toBeDefined()

    // No theme search box (the only textbox-shaped control was the theme/
    // marketplace search input) and no marketplace copy anywhere.
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByText(/marketplace/i)).toBeNull()
    // No skin/theme gallery card: even the one skin is never offered as a
    // choice (a gallery card would render its label + description).
    expect(screen.queryByText('Nadia')).toBeNull()
    expect(screen.queryByText('NadicodeAI design system')).toBeNull()
  })

  it('changing the appearance mode sets the mode and plays no haptic', () => {
    render(<AppearanceSettings />)

    fireEvent.click(screen.getByRole('button', { name: 'Dark' }))

    expect(setMode).toHaveBeenCalledWith('dark')
    expect(triggerHaptic).not.toHaveBeenCalled()
  })
})
