// Product-acceptance gate — drives the PACKAGED, shipping binary (not
// `electron .`) the way a user's machine runs it, and asserts it renders, is
// correctly renamed, and can start portal activation.
//
// The renderer-mount smoke (assert-renderer-mounts.mjs) launches the dev main
// against the freshly built dist/. That catches a bundle that throws at load,
// but it never exercises the thing we actually ship: the electron-builder
// output — asar-packed, code-signed, name-rewritten nadia→nadia, first-run
// bootstrap and all. This gate attaches over CDP to the real executable and:
//
//   render : the React tree mounted AND painted non-trivial text (not a blank
//            or error-boundary-swallowed window).
//   brand  : the rendered title + body carry the Nadia identity and NO legacy
//            Nadia/Nadia text — the rename is verified against pixels, not grep.
//   portal : first-run only. Wait out the bootstrap, then click the NadicodeAI
//            Portal sign-in and assert device-code activation actually starts
//            (issue #14: clicking mid-bootstrap used to error "Could not reach
//            the NadicodeAI Portal"). If it still errors, the gate fails with
//            the on-screen text verbatim.
//
// CLI (fixed):
//   node scripts/product-gate.mjs --binary "<path to packaged executable>" \
//     [--pristine] [--checks render,brand,portal] [--port N]
//
// Exit 0 = every requested check passed (one ✓ line each). Exit 1 = the first
// failing check, named, with the evidence lines that condemned it.

import { spawn, spawnSync } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import { fileURLToPath } from 'node:url'

const SCRIPT = fileURLToPath(import.meta.url)

// ── args ──────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2)
function opt(name, fallback) {
  const i = argv.indexOf(name)
  return i >= 0 && i + 1 < argv.length ? argv[i + 1] : fallback
}
function has(name) { return argv.includes(name) }

const BINARY = opt('--binary')
const PORT = Number.parseInt(opt('--port', '9340'), 10) || 9340
const CHECKS = String(opt('--checks', 'render,brand'))
  .split(',').map(s => s.trim()).filter(Boolean)
const WANT_PORTAL = CHECKS.includes('portal')
// --pristine (a real first run: throwaway home) and portal both want an
// isolated home. The gate now isolates unconditionally (see launch section),
// so this flag is accepted for the documented CLI but no longer gates it.
void has('--pristine')

const KNOWN_CHECKS = new Set(['render', 'brand', 'portal'])
const BOOT_TIMEOUT_MS = 60000
const RENDER_SETTLE_MS = 4000
const BODY_TEXT_MIN = 40
const PORTAL_FIRSTRUN_TIMEOUT_MS = 5 * 60 * 1000  // first run may download+install a backend
const PORTAL_ACTIVATION_TIMEOUT_MS = 60 * 1000

// ── cleanup: kill spawned process + temp dir on EVERY exit path ─────────────
let child = null
let tmpDir = null
function cleanup() {
  if (child) { try { child.kill('SIGKILL') } catch {} child = null }
  if (tmpDir) { try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch {} tmpDir = null }
}
process.on('exit', cleanup)
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { cleanup(); process.exit(1) })

function die(msg) {
  console.error(`\n✗ product-gate FAILED\n  ${msg}\n`)
  cleanup()
  process.exit(1)
}
function fail(check, evidence) {
  die(`check "${check}" failed.\n  ${String(evidence).split('\n').join('\n  ')}`)
}
function ok(line) { console.log(`✓ ${line}`) }

if (!BINARY) die('missing required --binary "<path to packaged executable>"')
if (!fs.existsSync(BINARY)) die(`--binary does not exist: ${BINARY}`)
for (const c of CHECKS) if (!KNOWN_CHECKS.has(c)) die(`unknown check "${c}" (known: render, brand, portal)`)

// ── Linux headless: never skip — re-exec under xvfb like the smoke does ─────
if (process.platform === 'linux' && !process.env.DISPLAY && !process.env.__PRODUCT_GATE_XVFB) {
  const hasXvfb = spawnSync('sh', ['-c', 'command -v xvfb-run']).status === 0
  if (!hasXvfb) {
    die('no DISPLAY and xvfb-run not installed — the product gate cannot run.\n  ' +
        'Install xvfb (e.g. `apt-get install -y xvfb`) so acceptance can verify the packaged app.')
  }
  const r = spawnSync('xvfb-run', ['-a', process.execPath, SCRIPT, ...argv], {
    stdio: 'inherit',
    env: { ...process.env, __PRODUCT_GATE_XVFB: '1' }
  })
  process.exit(r.status ?? 1)
}

// ── launch the packaged binary ──────────────────────────────────────────────
const binArgs = [`--remote-debugging-port=${PORT}`]
const env = { ...process.env }
// Clear any dev-server pointer so the packaged renderer loads its own bundle.
env.NADIA_DESKTOP_DEV_SERVER = ''
env.NADIA_DESKTOP_DEV_SERVER = ''

// Always run the binary against a throwaway userData + home, even without
// --pristine. An acceptance gate must measure the BUILD, not the operator's
// disk: with the real home the app's workspace file-browser lists $HOME, and a
// developer machine that has a leftover ~/.nadia (or ~/.nous) directory then
// fails the brand check on a file name that has nothing to do with the build.
// Isolation makes render/brand hermetic; it is also exactly what a first run
// needs, so --pristine/portal get it for free. (macOS ignores $HOME for
// Chromium userData, so the --user-data-dir flag is required; the *_HOME env is
// what the backend reads. Both name states are set because the packaged build
// may be pre- or post-rename. Proven empirically.)
tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nadia-product-gate-'))
const userData = path.join(tmpDir, 'user-data')
const home = path.join(tmpDir, 'home')
fs.mkdirSync(userData, { recursive: true })
fs.mkdirSync(home, { recursive: true })
binArgs.push(`--user-data-dir=${userData}`)
env.NADIA_HOME = home
env.NADIA_HOME = home

// render/brand only need the shell mounted; fake the backend boot so it is fast
// and deterministic (no real gateway). portal is a genuine first run — it must
// NOT fake-boot, or the onboarding/bootstrap surface never appears.
if (!WANT_PORTAL) {
  env.NADIA_DESKTOP_BOOT_FAKE = '1'
  env.NADIA_DESKTOP_BOOT_FAKE = '1'
}

child = spawn(BINARY, binArgs, { env, stdio: ['ignore', 'pipe', 'pipe'] })
let appLog = ''
child.stdout.on('data', d => { appLog += d })
child.stderr.on('data', d => { appLog += d })
child.on('error', e => die(`could not launch --binary: ${e.message}`))

// ── CDP plumbing (WebSocket, mirrors the smoke) ─────────────────────────────
async function cdpPage(port) {
  const deadline = Date.now() + BOOT_TIMEOUT_MS
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/list`)
      const list = await r.json()
      const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl)
      if (page) return page
    } catch {}
    await new Promise(r => setTimeout(r, 500))
  }
  return null
}

const page = await cdpPage(PORT)
if (!page) fail('render', `packaged app did not expose a renderer within ${BOOT_TIMEOUT_MS}ms.\n${appLog.slice(-800)}`)

const ws = new WebSocket(page.webSocketDebuggerUrl)
let msgId = 0
const pending = new Map()
const errors = []
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data)
  if (m.id != null && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
  if (m.method === 'Runtime.exceptionThrown') {
    errors.push(m.params?.exceptionDetails?.exception?.description || m.params?.exceptionDetails?.text || 'exception')
  }
})
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP ${method} timed out`)) }, BOOT_TIMEOUT_MS)
    pending.set(id, m => { clearTimeout(timer); resolve(m) })
    ws.send(JSON.stringify({ id, method, params }))
  })
}
// Evaluate an expression in the page, returning the parsed JSON value.
async function evalJSON(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  try { return JSON.parse(r.result?.result?.value ?? 'null') } catch { return null }
}

await new Promise(r => ws.addEventListener('open', r))
await send('Runtime.enable')

// A snapshot the checks poll against.
async function snapshot() {
  return (await evalJSON(`JSON.stringify({
    title: document.title,
    text: document.body ? document.body.innerText : '',
    buttons: [...document.querySelectorAll('button, a, [role=button]')]
      .map(b => (b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim()).filter(Boolean),
    hrefs: [...document.querySelectorAll('a[href]')].map(a => a.href)
  })`)) || { title: '', text: '', buttons: [], hrefs: [] }
}

const passed = []

// ── render ──────────────────────────────────────────────────────────────────
if (CHECKS.includes('render')) {
  await new Promise(r => setTimeout(r, RENDER_SETTLE_MS))
  const s = await evalJSON(`JSON.stringify({
    rootKids: document.getElementById('root')?.childElementCount ?? -1,
    bodyLen: document.body ? document.body.innerText.length : 0,
    crashed: (() => { const el = document.querySelector('[data-render-error]'); return el ? String(el.getAttribute('data-render-error') || 'render error') : null })()
  })`) || { rootKids: -1, bodyLen: 0, crashed: null }
  if (s.crashed) {
    fail('render', `the interface crashed into its error screen (root error boundary).\nBoundary error: ${s.crashed}`)
  }
  if ((s.rootKids ?? -1) < 1 || (s.bodyLen ?? 0) <= BODY_TEXT_MIN) {
    const uncaught = errors.find(e => /ReferenceError|is not defined|TypeError|SyntaxError/.test(e)) || errors[0]
    const why = (s.rootKids ?? -1) < 1
      ? `#root has no children — the React tree never mounted`
      : `#root mounted but only ${s.bodyLen} char(s) rendered (need > ${BODY_TEXT_MIN}) — a mounted-but-blank window`
    fail('render', `${why}.\nFirst uncaught exception: ${uncaught ? uncaught.split('\n')[0] : '(none captured)'}\n${appLog.slice(-500)}`)
  }
  ok(`render — #root has ${s.rootKids} child element(s), ${s.bodyLen} chars painted`)
  passed.push('render')
}

// ── brand ─────────────────────────────────────────────────────────────────
if (CHECKS.includes('brand')) {
  const b = await evalJSON(`JSON.stringify({ title: document.title, text: document.body ? document.body.innerText : '' })`)
    || { title: '', text: '' }
  const haystack = `${b.title}\n${b.text}`
  // Runtime-computed legacy tokens (see the note in assert-renderer-mounts.mjs:
  // a literal pattern gets transformed by build-time brand tooling and the
  // shipped gate would then hunt the CURRENT brand).
  const LEGACY = ['hermez'.replace('z', 's'), 'nouz'.replace('z', 's')]
  const LEGACY_RE = new RegExp('\\b(' + LEGACY.join('|') + ')\\b', 'gi')
  const LEGACY_RE_LINE = new RegExp('\\b(' + LEGACY.join('|') + ')\\b', 'i')
  const leaks = haystack.match(LEGACY_RE) || []
  if (leaks.length) {
    const lines = haystack.split('\n').filter(l => LEGACY_RE_LINE.test(l)).slice(0, 6)
    fail('brand', `packaged build shows legacy brand text (${leaks.length} hit(s): ` +
      `${[...new Set(leaks.map(s => s.toLowerCase()))].join(', ')}). The rename missed what the user sees.\n` +
      `Offending lines:\n${lines.join('\n')}`)
  }
  if (!/nadia/i.test(haystack)) {
    fail('brand', `packaged build renders no "Nadia" text at all — rename likely did not run over the renderer.`)
  }
  ok(`brand — Nadia present, no ${LEGACY.join('/')} in rendered UI`)
  passed.push('brand')
}

// ── portal (first-run activation) ───────────────────────────────────────────
if (CHECKS.includes('portal')) {
  const findSignIn = buttons => buttons.find(t => /sign in|accedi/i.test(t) && /portal/i.test(t))
  const REACH_ERR = /could not reach the .*portal|impossibile raggiungere il portale|could not reach the nadicodeai portal/i
  const ACTIVATION_STARTED = t =>
    /enter this code|inserisci l.* questo codice|waiting for you to authorize|in attesa della tua autorizzazione/i.test(t)

  // 1. Wait out first-run bootstrap until the sign-in surface appears (or an
  //    onboarding error already settled). First run may download+install a
  //    backend, so poll patiently.
  const deadline = Date.now() + PORTAL_FIRSTRUN_TIMEOUT_MS
  let s = await snapshot()
  let signIn = findSignIn(s.buttons)
  while (!signIn && Date.now() < deadline) {
    if (REACH_ERR.test(s.text)) {
      const line = s.text.split('\n').find(l => REACH_ERR.test(l)) || s.text.slice(0, 300)
      fail('portal', `onboarding surfaced a portal-unreachable error before sign-in was even clickable (issue #14).\n` +
        `On-screen text: "${line.trim()}"`)
    }
    await new Promise(r => setTimeout(r, 2500))
    s = await snapshot()
    signIn = findSignIn(s.buttons)
  }
  if (!signIn) {
    fail('portal', `no NadicodeAI Portal sign-in control appeared within ${Math.round(PORTAL_FIRSTRUN_TIMEOUT_MS / 60000)} min ` +
      `of first-run bootstrap.\nLast screen text:\n${s.text.slice(0, 600)}`)
  }

  // 2. Click it via CDP.
  const clicked = await evalJSON(`(() => {
    const els = [...document.querySelectorAll('button, a, [role=button]')]
    const el = els.find(e => {
      const t = (e.innerText || e.textContent || '').replace(/\\s+/g, ' ').trim()
      return /sign in|accedi/i.test(t) && /portal/i.test(t)
    })
    if (!el) return JSON.stringify({ clicked: false })
    el.click()
    return JSON.stringify({ clicked: true, label: (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim() })
  })()`)
  if (!clicked || !clicked.clicked) {
    fail('portal', `found a sign-in control ("${signIn}") but could not click it via CDP.`)
  }

  // 3. Within 60s: activation must start (device code / portal.nadicode.ai), or
  //    fail with the on-screen error verbatim (issue #14 honestly failing).
  const actDeadline = Date.now() + PORTAL_ACTIVATION_TIMEOUT_MS
  let started = false
  let lastText = ''
  while (Date.now() < actDeadline) {
    const cur = await snapshot()
    lastText = cur.text
    const reach = `${cur.text}\n${cur.hrefs.join(' ')}`
    if (REACH_ERR.test(cur.text)) {
      const line = cur.text.split('\n').find(l => REACH_ERR.test(l)) || cur.text.slice(0, 300)
      fail('portal', `clicking sign-in produced a portal-unreachable error (issue #14 — the gate honestly failing).\n` +
        `On-screen text: "${line.trim()}"`)
    }
    if (/portal\.nadicode\.ai/i.test(reach) || ACTIVATION_STARTED(cur.text)) { started = true; break }
    await new Promise(r => setTimeout(r, 2000))
  }
  if (!started) {
    fail('portal', `clicked "${clicked.label || signIn}" but no activation started within ` +
      `${PORTAL_ACTIVATION_TIMEOUT_MS / 1000}s (no device code, no portal.nadicode.ai).\n` +
      `Last screen text:\n${lastText.slice(0, 600)}`)
  }
  ok(`portal — sign-in clicked, portal activation started (device code / portal.nadicode.ai surfaced)`)
  passed.push('portal')
}

try { ws.close() } catch {}
cleanup()
console.log(`\nproduct-gate PASSED: ${passed.join(', ')}`)
process.exit(0)
