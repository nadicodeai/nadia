/*
 * Classify a raw Rust diagnostic (the string carried on a `failed` event or a
 * launch rejection) into a stable, localizable failure cause. The Rust worker
 * (src-tauri/src/{bootstrap,update}.rs) emits English prose, not machine codes;
 * this is the TS-side map from that prose to a catalog key — the same "map the
 * machine state on the frontend, never localize inside Rust" rule the progress
 * stages already follow.
 *
 * Matching is on rename-stable phrases plus both the dev ("Nadia") and shipped
 * ("Nadia", after the export rename) spellings, so it works in the built
 * product as well as in this nadia-named tree. Anything unrecognized returns
 * null → the route shows a localized generic headline with the raw diagnostic
 * demoted to a detail line, so no failure is ever silently swallowed.
 */
export type FailureCause =
  | 'alreadyRunning'
  | 'notInstalled'
  | 'rebuild'
  | 'desktopMissing'
  | 'gitMissing'
  | 'download'
  | 'disk'
  | 'permission'
  | 'cancelled'

export function classifyFailure(error: string | null | undefined): FailureCause | null {
  if (!error) {
    return null
  }
  // Match on failure *prose*, never on incidental tokens in a URL. Remedy links
  // routinely carry keyword paths (e.g. git-scm.com/download/win, nodejs.org/…
  // /download/), which would otherwise trip the network/download bucket and hand
  // the operator the wrong fix. Strip schemed URLs before any keyword test.
  const e = error.toLowerCase().replace(/https?:\/\/\S+/g, ' ')

  // Specific, distinctive phrases first (a message can contain several
  // keywords; the exact operator remedy wins over a generic keyword bucket).
  if (/\bcancell/.test(e)) {
    return 'cancelled'
  }
  if (/still running|close all (?:nadia|nadia) windows/.test(e)) {
    return 'alreadyRunning'
  }
  if (/find the (?:nadia|nadia) cli|is (?:nadia|nadia) installed/.test(e)) {
    return 'notInstalled'
  }
  if (/rebuilding the desktop app failed/.test(e)) {
    return 'rebuild'
  }
  if (/find a built (?:nadia|nadia) desktop|desktop build step/.test(e)) {
    return 'desktopMissing'
  }
  // Git absent and its auto-install failed (install.ps1 Stage-Git / install.sh,
  // forwarded verbatim by bootstrap.rs). The remedy is "install Git from the
  // shown link", not "check your network" — anchor on the stable phrasing, above
  // the download bucket.
  if (/git not available/.test(e)) {
    return 'gitMissing'
  }
  // Keyword buckets for the OS/environment failures the install scripts surface.
  if (/no space left|enospc|not enough space|insufficient (?:disk )?space|disk (?:is )?full/.test(e)) {
    return 'disk'
  }
  if (/permission denied|access is denied|eacces|eperm|not permitted|requires admin|elevat/.test(e)) {
    return 'permission'
  }
  if (
    /\bdownload|network|connection|timed out|could not resolve|resolve install script|enotfound|econnrefused|\bfetch|no such host|unable to connect/.test(
      e
    )
  ) {
    return 'download'
  }
  return null
}
