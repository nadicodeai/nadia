import { describe, expect, it as test } from 'vitest'

import { classifyFailure } from './failures'

/*
 * The classifier maps the ACTUAL diagnostics src-tauri emits (copied verbatim
 * from bootstrap.rs / update.rs) to stable cause keys. If Rust changes a
 * message the map still degrades safely to null (generic headline + raw
 * detail), but the known classes an operator hits most must keep their
 * plain-language explanation.
 */
describe('installer failure classifier', () => {
  test('already-running (update.rs concurrent guard, exit 2)', () => {
    expect(
      classifyFailure(
        'Nadia is still running. Close all Nadia windows and try the update again.'
      )
    ).toBe('alreadyRunning')
  })

  test('not-installed (update.rs resolve_nadia)', () => {
    expect(
      classifyFailure(
        'Could not find the nadia CLI under /Users/x/.nadia/nadia-agent. Is Nadia installed? Re-run the installer to repair the install.'
      )
    ).toBe('notInstalled')
  })

  test('rebuild-failed (update.rs desktop --build-only)', () => {
    expect(
      classifyFailure(
        'Rebuilding the desktop app failed (exit Some(1)). The update was applied but the app could not be rebuilt; run `nadia desktop` from a terminal to see the error.'
      )
    ).toBe('rebuild')
  })

  test('desktop-missing (bootstrap.rs launch_nadia_desktop)', () => {
    expect(
      classifyFailure(
        "Couldn't find a built Nadia desktop at /Users/x/.nadia/nadia-agent/apps/desktop/release. The desktop build step may have been skipped or failed. Run `nadia desktop` from a terminal to build and launch it."
      )
    ).toBe('desktopMissing')
  })

  test('download / network', () => {
    expect(classifyFailure('resolve install script failed: could not download install.ps1')).toBe(
      'download'
    )
    expect(classifyFailure('curl: (6) Could not resolve host: github.com')).toBe('download')
  })

  test('git-missing (install.ps1 Stage-Git, forwarded verbatim by bootstrap.rs)', () => {
    // The remedy URL literally contains "/download/" — this must NOT be read as
    // a network/download failure. Operator needs to install Git, not check wifi.
    expect(
      classifyFailure(
        'Git not available and auto-install failed -- install from https://git-scm.com/download/win then re-run'
      )
    ).toBe('gitMissing')
  })

  test('a URL in the body never trips a keyword matcher (URL-insensitive)', () => {
    // Unknown failure whose only "download"/keyword token lives inside a URL:
    // strip the URL first, fall through to null (generic headline + raw detail).
    expect(
      classifyFailure('Unexpected failure. See https://example.com/download/help for details.')
    ).toBeNull()
  })

  test('disk space', () => {
    expect(classifyFailure('write error: No space left on device (os error 28)')).toBe('disk')
    expect(classifyFailure('ENOSPC: no space left, write')).toBe('disk')
  })

  test('permission', () => {
    expect(classifyFailure('uv: Access is denied. (os error 5)')).toBe('permission')
    expect(classifyFailure('EACCES: permission denied, open')).toBe('permission')
  })

  test('cancelled by user', () => {
    expect(classifyFailure('cancelled by user')).toBe('cancelled')
    expect(classifyFailure('bootstrap cancelled by user')).toBe('cancelled')
  })

  test('post-rename spelling (shipped product says "Nadia") still classifies', () => {
    expect(
      classifyFailure('Nadia is still running. Close all Nadia windows and try the update again.')
    ).toBe('alreadyRunning')
    expect(
      classifyFailure("Couldn't find a built Nadia desktop. The desktop build step may have failed.")
    ).toBe('desktopMissing')
  })

  test('unknown diagnostics fall through to null (generic headline + raw detail)', () => {
    expect(classifyFailure('Segmentation fault at 0xdeadbeef')).toBeNull()
    expect(classifyFailure(null)).toBeNull()
    expect(classifyFailure('')).toBeNull()
  })
})
