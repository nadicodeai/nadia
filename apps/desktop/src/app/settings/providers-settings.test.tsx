import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { OAuthProvider } from '@/types/nadia'

const listOAuthProviders = vi.fn()
const disconnectOAuthProvider = vi.fn()
const startManualProviderOAuth = vi.fn()
const onboarding = atom({ manual: false })

vi.mock('@/nadia', () => ({
  disconnectOAuthProvider: (providerId: string) => disconnectOAuthProvider(providerId),
  listOAuthProviders: () => listOAuthProviders()
}))

vi.mock('@/store/onboarding', () => ({
  $desktopOnboarding: onboarding,
  startManualProviderOAuth: (providerId: string) => startManualProviderOAuth(providerId)
}))

function portal(loggedIn: boolean, patch: Partial<OAuthProvider> = {}): OAuthProvider {
  return {
    cli_command: 'nadia auth add nous',
    disconnectable: true,
    docs_url: '',
    flow: 'device_code',
    id: 'nous',
    name: 'NadicodeAI Portal',
    status: { logged_in: loggedIn },
    ...patch
  }
}

function thirdParty(id: string, name: string): OAuthProvider {
  return {
    cli_command: `nadia auth add ${id}`,
    disconnectable: true,
    docs_url: '',
    flow: 'device_code',
    id,
    name,
    status: { logged_in: true }
  }
}

beforeEach(() => {
  onboarding.set({ manual: false })
  disconnectOAuthProvider.mockResolvedValue({ ok: true, provider: 'nous' })
  listOAuthProviders.mockResolvedValue({
    providers: [portal(true), thirdParty('minimax-oauth', 'MiniMax')]
  })
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

async function renderProvidersSettings() {
  const { ProvidersSettings } = await import('./providers-settings')

  return render(<ProvidersSettings onClose={vi.fn()} onViewChange={vi.fn()} view="accounts" />)
}

describe('ProvidersSettings — portal-only', () => {
  it('renders only the NadicodeAI Portal card — third-party providers do not appear', async () => {
    await renderProvidersSettings()

    expect(await screen.findByText('NadicodeAI Portal')).toBeTruthy()
    expect(screen.queryByText('MiniMax')).toBeNull()
  })

  it('disconnects the connected portal account and refreshes the status', async () => {
    await renderProvidersSettings()

    const remove = await screen.findByRole('button', { name: 'Remove NadicodeAI Portal' })
    fireEvent.click(remove)

    await waitFor(() => expect(disconnectOAuthProvider).toHaveBeenCalledWith('nous'))
    await waitFor(() => expect(listOAuthProviders).toHaveBeenCalledTimes(2))
  })

  it('activates the portal when not connected', async () => {
    listOAuthProviders.mockResolvedValue({ providers: [portal(false)] })

    await renderProvidersSettings()

    expect(await screen.findByText(/Not connected/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Connect/ }))

    expect(startManualProviderOAuth).toHaveBeenCalledWith('nous')
    expect(disconnectOAuthProvider).not.toHaveBeenCalled()
  })
})
