import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { OnboardingContext, OnboardingFlow } from '@/store/onboarding'
import type { OAuthProvider } from '@/types/nadia'

import { FlowPanel } from './flow'

const portal: OAuthProvider = {
  cli_command: 'nadia login nadia',
  docs_url: 'https://portal.nadicode.ai',
  flow: 'device_code',
  id: 'nous',
  name: 'NadicodeAI Portal',
  status: { logged_in: false }
}

const ctx: OnboardingContext = { requestGateway: async () => undefined as never }

function renderFlow(flow: OnboardingFlow) {
  return render(<FlowPanel ctx={ctx} flow={flow} leaving={false} onBegin={() => {}} />)
}

afterEach(cleanup)

describe('activation failure states', () => {
  for (const cause of ['denied', 'expired', 'unreachable'] as const) {
    it(`explains a ${cause} activation in plain words and offers retry`, () => {
      renderFlow({ status: 'error', provider: portal, cause, message: `Sign-in ${cause}.` })

      // A plain-language explanation is shown (mentions activation, not a raw code).
      const explanation = screen.getByText(/activation/i)
      expect(explanation.textContent?.trim().length ?? 0).toBeGreaterThan(cause.length)

      // A retry action re-enters the device flow.
      expect(screen.getByRole('button', { name: /try again|retry/i })).toBeTruthy()

      // No third-party fallback / escape control.
      expect(screen.queryByRole('button', { name: /Pick a different provider/i })).toBeNull()
      expect(screen.queryByText(/OpenRouter/i)).toBeNull()
      expect(screen.queryByText(/API key/i)).toBeNull()
    })
  }
})
