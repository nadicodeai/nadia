import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

// Radix Select calls scrollIntoView / pointer-capture on its items when the
// content opens; jsdom implements none of these, so stub them to let the
// dropdown open in tests.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.releasePointerCapture = vi.fn()
})

const previewCompletionSound = vi.fn()
const triggerHaptic = vi.fn()

vi.mock('@/lib/completion-sound', () => ({
  COMPLETION_SOUND_VARIANTS: [
    { id: 1, name: 'Two-note comfort', play: vi.fn() },
    { id: 2, name: 'Soft bell', play: vi.fn() }
  ],
  previewCompletionSound: (variantId?: number) => previewCompletionSound(variantId)
}))

vi.mock('@/lib/haptics', () => ({
  triggerHaptic: (intent?: string) => triggerHaptic(intent)
}))

import { $completionSoundVariantId, setCompletionSoundVariantId } from '@/store/completion-sound'

import { NotificationsSettings } from './notifications-settings'

beforeEach(() => {
  previewCompletionSound.mockClear()
  triggerHaptic.mockClear()
  setCompletionSoundVariantId(1)
})

afterEach(cleanup)

describe('notifications settings — silent options, explicit preview', () => {
  it('changing the completion-sound variant plays no sound and no haptic', async () => {
    render(<NotificationsSettings />)

    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.click(await screen.findByRole('option', { name: 'Soft bell' }))

    // The selection actually took effect (variant 2) — so the handler ran.
    await waitFor(() => expect($completionSoundVariantId.get()).toBe(2))

    expect(previewCompletionSound).not.toHaveBeenCalled()
    expect(triggerHaptic).not.toHaveBeenCalled()
  })

  it('the explicit Preview button plays the selected chime', () => {
    render(<NotificationsSettings />)

    fireEvent.click(screen.getByRole('button', { name: /preview/i }))

    expect(previewCompletionSound).toHaveBeenCalled()
  })

  it('toggling a notification option flips the switch and plays no haptic', async () => {
    render(<NotificationsSettings />)

    const master = screen.getAllByRole('switch')[0]!
    const before = master.getAttribute('aria-checked')

    fireEvent.click(master)

    // The toggle actually flipped — so the change handler ran — silently.
    await waitFor(() => expect(master.getAttribute('aria-checked')).not.toBe(before))

    expect(triggerHaptic).not.toHaveBeenCalled()
    expect(previewCompletionSound).not.toHaveBeenCalled()
  })
})
