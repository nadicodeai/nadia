// Renderer-mount smoke test — the gate that would have caught the
// `cva$10 is not defined` blank-screen bug that shipped in every desktop
// release until v2026.7.6.
//
// Nothing else in the build launches the built renderer bundle in a real
// Chromium/V8 and looks at it: unit tests run in jsdom (which does not
// reproduce rolldown scope-hoisting faults), typecheck only type-checks, and
// test-desktop.mjs only verifies the packaged file layout. So a bundle that
// throws at module-eval — a white window for the user — passes every gate.
//
// This launches the actual app main with a faked backend boot (no gateway
// needed), attaches over CDP, and asserts the React app mounted (#root has
// children) with no uncaught error at load. Run automatically from the
// desktop `postbuild` step, so it covers CI, the release pipeline, and the
// build users run at install time.
//
// Exit 0 = renderer mounts. Exit 1 = blank/broken, with the console error.

import { spawn, spawnSync } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const DESKTOP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIST_INDEX = path.join(DESKTOP_ROOT, 'dist', 'index.html')
const PORT = 9339
const BOOT_TIMEOUT_MS = 45000
// A window can technically mount (#root gains a child) yet paint nothing —
// an empty shell or an error boundary that swallowed the tree. Require some
// real rendered text so "mounted but blank" still fails.
const MIN_BODY_TEXT_CHARS = 40

function fail(msg) {
  console.error(`\n✗ renderer-mount smoke FAILED\n  ${msg}\n`)
  process.exit(1)
}

if (!fs.existsSync(DIST_INDEX)) fail(`no built renderer at ${DIST_INDEX} — run \`vite build\` first`)

// Electron needs a display. On Linux CI there usually isn't one, so re-exec
// under xvfb-run. Never silently skip — if the gate cannot run, that must be a
// hard failure, otherwise it becomes the same invisible-gap that let the blank
// screen ship. macOS/Windows runners launch Electron directly.
if (process.platform === 'linux' && !process.env.DISPLAY && !process.env.__RENDERER_SMOKE_XVFB) {
  const hasXvfb = spawnSync('sh', ['-c', 'command -v xvfb-run']).status === 0
  if (!hasXvfb) {
    if (process.env.CI) {
      fail('no DISPLAY and xvfb-run not installed — the renderer gate cannot run.\n  ' +
           'Install xvfb (e.g. `apt-get install -y xvfb`) so packaging can verify the app renders.')
    }
    // End-user source build on a headless box (the install/update path builds
    // apps/desktop): a missing display must not brick the install — this build
    // class was already gated in CI and at release. Warn loudly, don't block.
    console.warn('⚠ renderer-mount smoke SKIPPED: no DISPLAY and no xvfb-run on a non-CI machine.\n' +
      '  The renderer was NOT verified on this box (CI and the release gate did). Install xvfb to enable.')
    process.exit(0)
  }
  const r = spawnSync('xvfb-run', ['-a', process.execPath, fileURLToPath(import.meta.url)], {
    stdio: 'inherit',
    env: { ...process.env, __RENDERER_SMOKE_XVFB: '1' }
  })
  process.exit(r.status ?? 1)
}

const electronBin = (await import('electron')).default
// Throwaway home: the smoke measures the BUILD, not the operator's disk. With
// the real HOME the app's file browser renders the operator's dotfiles (a
// leftover ~/.nadia directory NAME) straight into the brand check — same
// contamination product-gate.mjs isolates against. HOME works for the file
// browser (os.homedir()); *_HOME covers the backend paths on both name states.
const os = await import('node:os')
const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'renderer-smoke-home-'))
process.on('exit', () => { try { fs.rmSync(tmpHome, { recursive: true, force: true }) } catch {} })
const child = spawn(
  electronBin,
  ['.', `--remote-debugging-port=${PORT}`, `--user-data-dir=${path.join(tmpHome, 'user-data')}`],
  {
    cwd: DESKTOP_ROOT,
    // Fake the backend boot so the renderer mounts without a real gateway; the
    // cva-class fault we guard against throws at module-eval, before any
    // backend interaction, so a faked boot exercises exactly the failure mode.
    env: {
      ...process.env,
      NADIA_DESKTOP_BOOT_FAKE: '1', NADIA_DESKTOP_DEV_SERVER: '',
      HOME: tmpHome, NADIA_HOME: path.join(tmpHome, 'app-home'), NADIA_HOME: path.join(tmpHome, 'app-home')
    },
    stdio: ['ignore', 'pipe', 'pipe']
  }
)
let electronLog = ''
child.stdout.on('data', d => { electronLog += d })
child.stderr.on('data', d => { electronLog += d })

function cleanup() { try { child.kill('SIGKILL') } catch {} }
process.on('exit', cleanup)

async function cdp(port) {
  const deadline = Date.now() + BOOT_TIMEOUT_MS
  let list
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/list`)
      list = await r.json()
      const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl)
      if (page) return page
    } catch {}
    await new Promise(r => setTimeout(r, 500))
  }
  return null
}

const page = await cdp(PORT)
if (!page) { cleanup(); fail(`app did not expose a renderer within ${BOOT_TIMEOUT_MS}ms\n${electronLog.slice(-800)}`) }

const ws = new WebSocket(page.webSocketDebuggerUrl)
let id = 0
const pending = new Map()
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data)
  if (m.id != null && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
  if (m.method === 'Runtime.exceptionThrown') errors.push(m.params?.exceptionDetails?.exception?.description || m.params?.exceptionDetails?.text || 'exception')
})
const errors = []
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
await new Promise(r => ws.addEventListener('open', r))
await send('Runtime.enable')

// Give the bundle time to evaluate and mount.
await new Promise(r => setTimeout(r, 4000))

const res = await send('Runtime.evaluate', {
  expression: `JSON.stringify({
    rootKids: document.getElementById('root')?.childElementCount ?? -1,
    bodyLen: document.body.innerText.length,
    crashed: (() => { const el = document.querySelector('[data-render-error]'); return el ? String(el.getAttribute('data-render-error') || 'render error') : null })()
  })`,
  returnByValue: true
})

const state = JSON.parse(res.result?.result?.value || '{}')
const rootKids = state.rootKids ?? -1
const bodyLen = state.bodyLen ?? 0
// The root error boundary paints a perfectly readable crash screen — enough
// text to satisfy the size check. A crashed interface must never pass.
if (state.crashed) {
  cleanup()
  ws.close()
  fail(`renderer crashed into its error screen (root error boundary).\n  ` +
       `Boundary error: ${state.crashed}`)
}
if (rootKids < 1 || bodyLen <= MIN_BODY_TEXT_CHARS) {
  const consoleErr = errors.find(e => /ReferenceError|is not defined|TypeError|SyntaxError/.test(e))
  const why = rootKids < 1
    ? `#root has no children — the React tree never mounted`
    : `#root mounted but only ${bodyLen} char(s) of text rendered (need > ${MIN_BODY_TEXT_CHARS}) — a mounted-but-blank window`
  cleanup()
  ws.close()
  fail(`renderer did not render (#root childElementCount=${rootKids}, body text length=${bodyLen}).\n  ` +
       `${why}. This is a blank-window bug — the bundle likely threw at load.\n  ` +
       (consoleErr ? `First runtime error: ${consoleErr.split('\\n')[0]}` : `No console error captured; check the bundle.`))
}

// Brand check: on a RENAMED build (release pipeline sets NADIA_BRAND_CHECK=1),
// the running app must show the Nadia identity and NO legacy Nadia/Nadia text.
// This is the only place the nadia→nadia rename is verified against what a
// user actually sees, rather than by grepping source. Skipped on the
// nadia-named source tree, where legacy strings are expected pre-rename.
// MUST run while the CDP socket is still open — cleanup()/ws.close() happen
// only after this block, or the second Runtime.evaluate never settles and node
// dies on an unresolved top-level await (exit 13) instead of reaching a verdict.
if (process.env.NADIA_BRAND_CHECK === '1') {
  const brand = await send('Runtime.evaluate', {
    expression: `JSON.stringify({ text: document.body.innerText, title: document.title })`,
    returnByValue: true
  })
  const { text = '', title = '' } = JSON.parse(brand.result?.result?.value || '{}')
  const haystack = `${title}\n${text}`
  // Legacy tokens are computed at runtime so build-time brand tooling can
  // never transform this check into hunting the CURRENT brand: a literal
  // pattern here previously got rewritten in the branded build, and the
  // check then flagged the properly-branded app for showing its own name.
  const LEGACY = ['hermez'.replace('z', 's'), 'nouz'.replace('z', 's')]
  const LEGACY_RE = new RegExp('\\b(' + LEGACY.join('|') + ')\\b', 'gi')
  const LEGACY_RE_LINE = new RegExp('\\b(' + LEGACY.join('|') + ')\\b', 'i')
  const leaks = (haystack.match(LEGACY_RE) || [])
  if (leaks.length) {
    const sample = haystack.split('\n').filter(l => LEGACY_RE_LINE.test(l)).slice(0, 4)
    cleanup()
    ws.close()
    fail(`renamed build shows legacy brand text (${leaks.length} hit(s)): ${[...new Set(leaks.map(s => s.toLowerCase()))].join(', ')}\n  ` +
         `The rename did not cover what the user sees. Offending lines:\n    ${sample.join('\n    ')}`)
  }
  if (!/nadia/i.test(haystack)) {
    cleanup()
    ws.close()
    fail(`renamed build renders no "Nadia" text at all — rename likely did not run over the renderer.`)
  }
  console.log(`✓ brand check passed (Nadia present, no ${LEGACY.join('/')} in rendered UI)`)
}

cleanup()
ws.close()

console.log(`✓ renderer-mount smoke passed (#root has ${rootKids} child element(s), ${bodyLen} chars rendered)`)
process.exit(0)
