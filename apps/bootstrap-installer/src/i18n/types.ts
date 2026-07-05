/*
 * Installer i18n contract.
 *
 * The bootstrap installer ships English and Italian and follows the OS
 * language: an Italian OS gets the Italian installer, everything
 * else gets English. There is no in-app language picker — the installer never
 * offers a choice the rest of the product doesn't.
 *
 * `Catalog` is the typed shape every locale must satisfy in full: a missing
 * key is a compile error, so `en` and `it` can never drift out of structural
 * sync. Brand strings live in the catalog entries themselves.
 */

import type { FailureCause } from './failures'

export type Locale = 'en' | 'it'

/**
 * Stable machine names for install/update stages, emitted by the Rust worker
 * (src-tauri) which parses the platform install scripts. The union is the
 * cross-platform superset (install.ps1 + install.sh + the update flow); the
 * progress screen maps a name to a localized label and falls back to the
 * Rust-provided title for any name not in the catalog. Localization happens
 * here on the TS side — never inside Rust.
 */
export type StageName =
  | 'prerequisites'
  | 'uv'
  | 'python'
  | 'git'
  | 'node'
  | 'system-packages'
  | 'repository'
  | 'repo'
  | 'venv'
  | 'dependencies'
  | 'python-deps'
  | 'node-deps'
  | 'desktop'
  | 'path'
  | 'config'
  | 'config-templates'
  | 'platform-sdks'
  | 'bootstrap-marker'
  | 'setup'
  | 'configure'
  | 'gateway'
  | 'complete'
  | 'handoff'
  | 'update'
  | 'rebuild'
  | 'install'

export interface Catalog {
  welcome: {
    tagline: string
    installCta: string
  }
  progress: {
    titleInstall: string
    titleUpdate: string
    titleDone: string
    descInstall: string
    descUpdate: string
    stepsComplete: (done: number, total: number) => string
    liveOutput: string
    lineCount: (n: number) => string
    showDetails: string
    hideDetails: string
    cancel: string
    loading: string
  }
  success: {
    ready: string
    launchHintBefore: string
    launchHintAfter: string
    launch: string
    launching: string
    launchErrorTitle: string
    /** Generic launch-failure body shown when the raw diagnostic maps to no
     * known cause — the raw string is still shown, demoted to a detail line. */
    launchErrorGeneric: string
  }
  failure: {
    titleInstall: string
    titleUpdate: string
    defaultErrorInstall: string
    defaultErrorUpdate: string
    retryInstall: string
    retryUpdate: string
    openLogs: string
    logLabel: string
  }
  stages: Record<StageName, string>
  /** Plain-language explanation per known failure cause (see ./failures). The
   * route shows one of these as the primary line and demotes the raw Rust
   * diagnostic to a secondary detail; an unknown cause uses the section's
   * generic message instead. */
  causes: Record<FailureCause, string>
  /** Label prefixing the demoted raw diagnostic on the failure/success routes. */
  errorDetailLabel: string
}
