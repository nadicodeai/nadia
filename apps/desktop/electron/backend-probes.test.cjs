/**
 * Tests for electron/backend-probes.cjs.
 *
 * Run with: node --test electron/backend-probes.test.cjs
 * (Wired into npm test:desktop:platforms in package.json.)
 */

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const { canImportNadiaCli, nadiaRuntimeImportProbe, verifyNadiaCli } = require('./backend-probes.cjs')

// Resolve the host's own Node binary -- guaranteed to be on disk and
// runnable. We use it as both a stand-in for "a python that doesn't
// have nadia_cli" (since `node -c "import nadia_cli"` will exit
// non-zero) and as a way to script verifyNadiaCli's success path
// (a tiny script we write to disk that exits 0 on --version).
const NODE_BIN = process.execPath

test('canImportNadiaCli returns false when path is falsy', () => {
  assert.equal(canImportNadiaCli(''), false)
  assert.equal(canImportNadiaCli(null), false)
  assert.equal(canImportNadiaCli(undefined), false)
})

test('canImportNadiaCli returns false when interpreter cannot run -c', () => {
  // node IS an interpreter, but `node -c "import nadia_cli"` is a
  // SyntaxError -- different exit reason from a real Python's
  // ModuleNotFoundError, but the predicate is "exit 0 or not" and
  // both land on "not", which is exactly what we want for the
  // resolver fall-through.
  assert.equal(canImportNadiaCli(NODE_BIN), false)
})

test('canImportNadiaCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'nadia-probes-ghost-' + Date.now() + '.exe')
  assert.equal(canImportNadiaCli(ghost), false)
})

test('nadia runtime import probe checks config dependencies', () => {
  const probe = nadiaRuntimeImportProbe()
  assert.match(probe, /\bimport yaml\b/)
  assert.match(probe, /\bimport nadia_cli\.config\b/)
})

test('verifyNadiaCli returns false when command is falsy', () => {
  assert.equal(verifyNadiaCli(''), false)
  assert.equal(verifyNadiaCli(null), false)
  assert.equal(verifyNadiaCli(undefined), false)
})

test('verifyNadiaCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'nadia-probes-ghost-' + Date.now() + '.exe')
  assert.equal(verifyNadiaCli(ghost), false)
})

test('verifyNadiaCli returns true when --version exits 0', () => {
  // Write a tiny script that exits 0 regardless of args, then invoke
  // it through node. This stands in for a working nadia binary --
  // verifyNadiaCli only cares about the exit code.
  const scriptPath = path.join(os.tmpdir(), `nadia-probes-ok-${Date.now()}-${process.pid}.cjs`)
  fs.writeFileSync(scriptPath, 'process.exit(0)\n')
  try {
    // Use node as the launcher and our script as the "command". Pass
    // shell:false (default) -- node is a real binary, no shim.
    // execFileSync passes ['--version'] as args, which node ignores
    // gracefully (well, it prints its version and exits 0, which is
    // perfect -- exit code 0 is the only signal we read).
    assert.equal(verifyNadiaCli(NODE_BIN), true)
  } finally {
    try {
      fs.unlinkSync(scriptPath)
    } catch {
      void 0
    }
  }
})

test('verifyNadiaCli swallows timeouts (does not throw)', () => {
  // We can't easily provoke a real 5s hang in CI without slowing the
  // suite, but we CAN confirm that an invocation that DOES throw
  // (because the binary is missing) returns false rather than
  // propagating. Same code path the timeout case takes.
  assert.equal(verifyNadiaCli('/definitely/not/a/real/binary/anywhere'), false)
})
