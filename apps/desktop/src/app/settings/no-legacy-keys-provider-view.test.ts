import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

// Provider settings is portal-only — there is
// no separate "API keys" view distinct from the single Accounts/portal card.
describe('settings has no legacy "API Keys" provider view', () => {
  it('providers-settings offers a single provider view', () => {
    const source = readFileSync(join(process.cwd(), 'src/app/settings/providers-settings.tsx'), 'utf8')

    expect(source).not.toMatch(/PROVIDER_VIEWS\s*=\s*\[[^\]]*'keys'/)
  })

  it('the settings sidebar renders no API-keys provider subnav item', () => {
    const source = readFileSync(join(process.cwd(), 'src/app/settings/index.tsx'), 'utf8')

    expect(source).not.toMatch(/providerApiKeys|providerView === 'keys'|openProviderView\('keys'\)/)
  })

  it('the command palette offers no API-keys provider entry', () => {
    const source = readFileSync(join(process.cwd(), 'src/app/command-palette/index.tsx'), 'utf8')

    expect(source).not.toMatch(/labelKey:\s*'providerApiKeys'|pview=keys/)
  })
})
