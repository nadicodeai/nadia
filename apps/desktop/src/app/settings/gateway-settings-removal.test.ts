import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const settingsDir = path.dirname(fileURLToPath(import.meta.url))
const appDir = path.resolve(settingsDir, '..')

function readSource(...parts: string[]) {
  return fs.readFileSync(path.join(...parts), 'utf8')
}

describe('desktop local gateway settings surface', () => {
  it('does not expose a gateway-settings module', () => {
    expect(fs.existsSync(path.join(settingsDir, 'gateway-settings.tsx'))).toBe(false)
  })

  it('does not register a gateway section in settings navigation', () => {
    const settingsSource = readSource(settingsDir, 'index.tsx')
    const settingsTypesSource = readSource(settingsDir, 'types.ts')
    const commandPaletteSource = readSource(appDir, 'command-palette', 'index.tsx')

    expect(settingsSource).not.toContain("from './gateway-settings'")
    expect(settingsSource).not.toContain("'gateway',")
    expect(settingsSource).not.toContain("activeView === 'gateway'")
    expect(settingsSource).not.toContain("setActiveView('gateway')")
    expect(settingsSource).not.toContain('t.settings.nav.gateway')
    expect(settingsSource).not.toContain('<GatewaySettings')
    expect(settingsTypesSource).not.toContain("| 'gateway'")
    expect(commandPaletteSource).not.toContain("labelKey: 'gateway'")
    expect(commandPaletteSource).not.toContain("tab: 'gateway'")
  })
})
