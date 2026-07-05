import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

// vitest runs with cwd at the desktop workspace root (apps/desktop).
const src = (rel: string) => join(process.cwd(), 'src', rel)
const read = (rel: string) => readFileSync(src(rel), 'utf8')

describe('portal surfaces — source shape', () => {
  it('the rebuilt onboarding surface consumes @nadicodeai/ui components', () => {
    expect(read('components/onboarding/index.tsx')).toMatch(/from '@nadicodeai\/ui'/)
  })

  it('the rebuilt provider settings surface consumes @nadicodeai/ui components', () => {
    expect(read('app/settings/providers-settings.tsx')).toMatch(/from '@nadicodeai\/ui'/)
  })

  it('drops the third-party provider card module and API-key catalog', () => {
    // The multi-provider card module (featured/other/OpenRouter rows + the
    // PROVIDER_DISPLAY override) is retired — the portal payload label is
    // authoritative post-A.
    expect(existsSync(src('components/onboarding/providers.tsx'))).toBe(false)

    const index = read('components/onboarding/index.tsx')
    expect(index).not.toMatch(/API_KEY_OPTIONS/)
    expect(index).not.toMatch(/useApiKeyCatalog/)
  })
})
