// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { EnvVarInfo } from '@/types/nadia'

// Guards the render-level exclusion: the 5
// non-model-integration keys must never surface a credential card in the
// Tools & Keys settings, even though the backend still returns them in the
// `tool` category alongside legitimate tool keys (e.g. a GitHub token).
const getEnvVars = vi.fn()

vi.mock('@/nadia', () => ({
  getEnvVars: () => getEnvVars(),
  setEnvVar: vi.fn(),
  deleteEnvVar: vi.fn(),
  revealEnvVar: vi.fn()
}))

vi.mock('@/store/notifications', () => ({
  notify: vi.fn(),
  notifyError: vi.fn()
}))

function envVar(overrides: Partial<EnvVarInfo> = {}): EnvVarInfo {
  return {
    advanced: false,
    category: 'tool',
    description: '',
    is_password: true,
    is_set: false,
    redacted_value: null,
    tools: [],
    url: null,
    ...overrides
  }
}

beforeEach(() => {
  getEnvVars.mockResolvedValue({
    FAL_KEY: envVar(),
    KREA_API_KEY: envVar(),
    VOICE_TOOLS_OPENAI_KEY: envVar(),
    ELEVENLABS_API_KEY: envVar(),
    MISTRAL_API_KEY: envVar(),
    GITHUB_TOKEN: envVar()
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('KeysSettings — non-model-integration key exclusion', () => {
  it('renders no card for the 5 non-model-integration keys but does render a legitimate tool key', async () => {
    const { KeysSettings } = await import('./keys-settings')
    const { container } = render(<KeysSettings view="tools" />)

    // GITHUB_TOKEN -> credentialRowLabel strips the _TOKEN suffix -> "GITHUB".
    expect(await screen.findByText('GITHUB')).toBeTruthy()

    // credentialRowLabel strips the _API_KEY/_TOKEN/_KEY suffix for each.
    expect(screen.queryByText('FAL')).toBeNull()
    expect(screen.queryByText('KREA')).toBeNull()
    expect(screen.queryByText('VOICE TOOLS OPENAI')).toBeNull()
    expect(screen.queryByText('ELEVENLABS')).toBeNull()
    expect(screen.queryByText('MISTRAL')).toBeNull()

    // Exactly one credential card rendered — the excluded keys are dropped
    // entirely from the group, not just relabeled or hidden behind a toggle.
    // Each rendered card is a direct child of the `tools` group's grid.
    expect(container.querySelectorAll('.grid.gap-2 > *')).toHaveLength(1)
  })
})
