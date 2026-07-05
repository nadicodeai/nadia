import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { $desktopOnboarding, type DesktopOnboardingState, type OnboardingContext } from '@/store/onboarding'
import type { OAuthProvider } from '@/types/nadia'

import { Picker } from '.'

function provider(id: string, name = id): OAuthProvider {
  return {
    cli_command: `nadia login ${id}`,
    docs_url: `https://example.com/${id}`,
    flow: 'device_code',
    id,
    name,
    status: { logged_in: false }
  }
}

function setProviders(providers: OAuthProvider[], patch: Partial<DesktopOnboardingState> = {}) {
  $desktopOnboarding.set({
    configured: false,
    flow: { status: 'idle' },
    mode: 'oauth',
    providers,
    reason: null,
    requested: false,
    firstRunSkipped: false,
    manual: false,
    localEndpoint: false,
    ...patch
  } satisfies DesktopOnboardingState)
}

const ctx: OnboardingContext = { requestGateway: async () => undefined as never }

afterEach(() => {
  cleanup()

  try {
    window.localStorage.clear()
  } catch {
    // jsdom localStorage should always be present; ignore if not.
  }

  $desktopOnboarding.set({
    configured: null,
    flow: { status: 'idle' },
    mode: 'oauth',
    providers: null,
    reason: null,
    requested: false,
    firstRunSkipped: false,
    manual: false,
    localEndpoint: false
  })
})

describe('onboarding Picker — portal-only', () => {
  it('offers a single NadicodeAI Portal sign-in and no third-party provider path', () => {
    setProviders([provider('anthropic', 'Anthropic Claude'), provider('nous', 'NadicodeAI Portal')])
    render(<Picker ctx={ctx} />)

    // Exactly one provider path: the portal sign-in.
    expect(screen.getByRole('button', { name: /Sign in with NadicodeAI Portal/ })).toBeTruthy()

    // No third-party provider surfaces, no API-key catalog, no disclosure.
    expect(screen.queryByText('Anthropic Claude')).toBeNull()
    expect(screen.queryByText('Anthropic API Key')).toBeNull()
    expect(screen.queryByText('OpenRouter')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Other providers' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'I have an API key' })).toBeNull()
  })

  it('renders the portal sign-in when only the portal provider is present', () => {
    setProviders([provider('nous', 'NadicodeAI Portal')])
    render(<Picker ctx={ctx} />)

    expect(screen.getByRole('button', { name: /Sign in with NadicodeAI Portal/ })).toBeTruthy()
  })

  it('offers "choose later" on first run and persists the skip', () => {
    setProviders([provider('nous', 'NadicodeAI Portal')])
    render(<Picker ctx={ctx} />)

    const skip = screen.getByRole('button', { name: "I'll choose a provider later" })

    fireEvent.click(skip)

    expect($desktopOnboarding.get().firstRunSkipped).toBe(true)
    expect(window.localStorage.getItem('nadia-onboarding-skipped-v1')).toBe('1')
  })

  it('hides "choose later" in manual (add-provider) mode', () => {
    setProviders([provider('nous', 'NadicodeAI Portal')], { manual: true })
    render(<Picker ctx={ctx} />)

    expect(screen.queryByRole('button', { name: "I'll choose a provider later" })).toBeNull()
  })
})
