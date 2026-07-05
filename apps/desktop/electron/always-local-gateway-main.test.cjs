'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const MAIN_PATH = path.join(__dirname, 'main.cjs')
const NORMALIZED_CONNECTION_CONFIG = { mode: 'local', remote: {}, profiles: {} }
// What a FRESH read of that same normalized connection.json looks like:
// readDesktopConnectionConfig's parse path always stamps a default authMode
// onto `remote` (pre-existing behavior, not specific to normalization) even
// when the saved block is otherwise empty. That stamp is transient — it's
// never written back to disk — so it shows up only on an in-memory re-read,
// not in the JSON file itself.
const NORMALIZED_CONNECTION_CONFIG_REREAD = { mode: 'local', remote: { authMode: 'token' }, profiles: {} }

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function plain(value) {
  return JSON.parse(JSON.stringify(value))
}

function writeConnectionFixture(userDataDir, config) {
  fs.mkdirSync(userDataDir, { recursive: true })
  fs.writeFileSync(path.join(userDataDir, 'connection.json'), JSON.stringify(config, null, 2))
}

function extractConnectionRegion() {
  const source = fs.readFileSync(MAIN_PATH, 'utf8')
  const start = source.indexOf('function encryptDesktopSecret(value) {')
  const end = source.indexOf("// GET a profile's resolved backend", start)

  assert.notEqual(start, -1, 'main.cjs connection helper start marker was not found')
  assert.notEqual(end, -1, 'main.cjs connection helper end marker was not found')

  return source.slice(start, end)
}

function loadConnectionRegion(userDataDir, env = {}) {
  const writeCalls = []
  const module = { exports: {} }
  const harnessSource = `
    'use strict'
    const fs = require('node:fs')
    const path = require('node:path')
    const {
      buildGatewayWsUrl,
      buildGatewayWsUrlWithTicket,
      connectionScopeKey,
      normAuthMode,
      normalizeRemoteBaseUrl,
      profileRemoteOverride,
      resolveAuthMode,
      tokenPreview
    } = require('./connection-config.cjs')

    const DESKTOP_CONNECTION_CONFIG_PATH = path.join(process.env.NADIA_DESKTOP_USER_DATA_DIR, 'connection.json')
    const DESKTOP_PROFILE_CONFIG_PATH = path.join(process.env.NADIA_DESKTOP_USER_DATA_DIR, 'active-profile.json')
    const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/
    const safeStorage = {
      decryptString(value) {
        return Buffer.from(value).toString('utf8')
      },
      encryptString(value) {
        return Buffer.from(String(value), 'utf8')
      }
    }
    let connectionConfigCache = null
    let connectionConfigCacheMtime = null

    function writeFileAtomic(targetPath, data, encoding = 'utf8') {
      __writeCalls.push({ data, targetPath })
      fs.writeFileSync(targetPath, data, encoding)
    }

    function encryptDesktopSecretStrict(value) {
      return { encoding: 'plain', value: String(value || '') }
    }

    async function hasLiveOauthSession() {
      return true
    }

    async function mintGatewayWsTicket() {
      return 'test-ticket'
    }

    ${extractConnectionRegion()}

    module.exports = {
      __writeCalls,
      readDesktopConnectionConfig,
      resolveRemoteBackend,
      writeDesktopConnectionConfig
    }
  `

  const context = vm.createContext({
    Buffer,
    URL,
    __dirname,
    __writeCalls: writeCalls,
    console,
    module,
    process: {
      env: {
        ...process.env,
        NADIA_DESKTOP_USER_DATA_DIR: userDataDir,
        ...env
      },
      platform: process.platform
    },
    require(specifier) {
      if (specifier === './connection-config.cjs') {
        return require(path.join(__dirname, 'connection-config.cjs'))
      }
      return require(specifier)
    }
  })

  vm.runInContext(harnessSource, context, { filename: MAIN_PATH })

  return module.exports
}

test('resolveRemoteBackend ignores stored global remote mode when no env override is set', async t => {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nadia-desktop-local-gateway-'))
  t.after(() => fs.rmSync(userDataDir, { force: true, recursive: true }))

  writeConnectionFixture(userDataDir, {
    mode: 'remote',
    remote: {
      authMode: 'token',
      token: { encoding: 'plain', value: 'saved-token' },
      url: 'https://saved-gateway.example.com/nadia'
    },
    profiles: {}
  })

  const harness = loadConnectionRegion(userDataDir, {
    NADIA_DESKTOP_REMOTE_TOKEN: '',
    NADIA_DESKTOP_REMOTE_URL: ''
  })

  assert.equal(await harness.resolveRemoteBackend(null), null)
})

test('resolveRemoteBackend still honors the desktop env remote override', async t => {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nadia-desktop-local-gateway-'))
  t.after(() => fs.rmSync(userDataDir, { force: true, recursive: true }))

  writeConnectionFixture(userDataDir, {
    mode: 'local',
    remote: {},
    profiles: {}
  })

  const harness = loadConnectionRegion(userDataDir, {
    NADIA_DESKTOP_REMOTE_TOKEN: 'env-token',
    NADIA_DESKTOP_REMOTE_URL: 'https://env-gateway.example.com/nadia/'
  })

  assert.deepEqual(plain(await harness.resolveRemoteBackend(null)), {
    authMode: 'token',
    baseUrl: 'https://env-gateway.example.com/nadia',
    mode: 'remote',
    source: 'env',
    token: 'env-token',
    wsUrl: 'wss://env-gateway.example.com/nadia/api/ws?token=env-token'
  })
})

const staleRemoteCases = [
  {
    name: 'global remote mode',
    config: {
      mode: 'remote',
      remote: {},
      profiles: {}
    }
  },
  {
    name: 'saved global remote block',
    config: {
      mode: 'local',
      remote: {
        authMode: 'token',
        token: { encoding: 'plain', value: 'saved-token' },
        url: 'https://saved-gateway.example.com/nadia'
      },
      profiles: {}
    }
  },
  {
    name: 'per-profile remote overrides',
    config: {
      mode: 'local',
      remote: {},
      profiles: {
        coder: {
          authMode: 'token',
          mode: 'remote',
          token: { encoding: 'plain', value: 'profile-token' },
          url: 'https://profile-gateway.example.com/nadia'
        }
      }
    }
  },
  {
    name: 'malformed remote block (wrong-shape keys)',
    config: {
      mode: 'local',
      remote: {
        baseUrl: 'https://saved-gateway.example.com/nadia',
        sessionToken: 'saved-token'
      },
      profiles: {}
    }
  },
  {
    name: 'malformed remote block (array)',
    config: {
      mode: 'local',
      remote: ['unexpected'],
      profiles: {}
    }
  }
]

for (const { config, name } of staleRemoteCases) {
  test(`startup connection config load normalizes stale ${name}`, t => {
    const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nadia-desktop-local-gateway-'))
    const connectionPath = path.join(userDataDir, 'connection.json')
    t.after(() => fs.rmSync(userDataDir, { force: true, recursive: true }))

    writeConnectionFixture(userDataDir, config)

    const firstStartup = loadConnectionRegion(userDataDir, {
      NADIA_DESKTOP_REMOTE_TOKEN: '',
      NADIA_DESKTOP_REMOTE_URL: ''
    })

    // plain(): readDesktopConnectionConfig() runs inside the vm context built by
    // loadConnectionRegion, so its return value's plain objects belong to that
    // context's realm. node:assert/strict's deepEqual (deepStrictEqual) treats
    // structurally-identical objects from different realms as unequal, so
    // normalize through JSON before comparing against an outer-realm literal —
    // same technique the resolveRemoteBackend tests above already use.
    assert.deepEqual(plain(firstStartup.readDesktopConnectionConfig()), NORMALIZED_CONNECTION_CONFIG)
    assert.deepEqual(readJson(connectionPath), NORMALIZED_CONNECTION_CONFIG)
    assert.ok(firstStartup.__writeCalls.length >= 1, 'normalization should persist through the connection config write path')

    const secondStartup = loadConnectionRegion(userDataDir, {
      NADIA_DESKTOP_REMOTE_TOKEN: '',
      NADIA_DESKTOP_REMOTE_URL: ''
    })

    assert.deepEqual(plain(secondStartup.readDesktopConnectionConfig()), NORMALIZED_CONNECTION_CONFIG_REREAD)
    assert.deepEqual(readJson(connectionPath), NORMALIZED_CONNECTION_CONFIG)
  })
}
