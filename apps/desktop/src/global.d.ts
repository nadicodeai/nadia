export {}

declare global {
  interface Window {
    nadiaDesktop: {
      // Resolve a backend connection. Omit `profile` (or pass the primary) for
      // the window's backend; pass a named profile to lazily spawn/reuse that
      // profile's backend from the pool.
      getConnection: (profile?: string | null) => Promise<NadiaConnection>
      // Reconnect-after-wake recovery: liveness-probe the cached PRIMARY backend
      // and drop it if a remote one has gone unreachable, so the next
      // getConnection() rebuilds a reachable descriptor instead of the renderer
      // re-dialing a dead remote forever. No-op for local backends (they
      // self-heal via the child 'exit' handler). `rebuilt` is true when a stale
      // remote cache was dropped.
      revalidateConnection: () => Promise<{ ok: boolean; rebuilt: boolean }>
      // Keepalive: mark a pool profile backend as recently used so the idle
      // reaper spares it while its chat is active.
      touchBackend: (profile?: string | null) => Promise<{ ok: boolean }>
      getGatewayWsUrl: (profile?: null | string) => Promise<string>
      // Open (or focus) a standalone OS window for a single chat session so
      // the user can work with multiple chats side by side. Returns ok:false
      // with an error code when the sessionId is empty/invalid. `watch` opens
      // a spectator window (lazy resume — no agent build) for live-streaming
      // a running subagent's session.
      openSessionWindow: (sessionId: string, opts?: { watch?: boolean }) => Promise<{ ok: boolean; error?: string }>
      // Open (or focus) a compact secondary window on the new-session draft.
      openNewSessionWindow: () => Promise<{ ok: boolean; error?: string }>
      getBootProgress: () => Promise<DesktopBootProgress>
      getConnectionConfig: (profile?: null | string) => Promise<DesktopConnectionConfig>
      applyConnectionConfig: (payload: DesktopConnectionConfigInput) => Promise<DesktopConnectionConfig>
      probeConnectionConfig: (remoteUrl: string) => Promise<DesktopConnectionProbeResult>
      oauthLoginConnectionConfig: (remoteUrl: string) => Promise<DesktopOauthLoginResult>
      // saveConnectionConfig/testConnectionConfig/oauthLogoutConnectionConfig
      // removed with the gateway-settings UI (always-local desktop).
      profile: {
        get: () => Promise<DesktopActiveProfile>
        // Persists the desktop's profile choice and relaunches the local
        // backend under the new NADIA_HOME (reloads the window). Pass null to
        // clear the preference.
        set: (name: string | null) => Promise<DesktopActiveProfile>
      }
      api: <T>(request: NadiaApiRequest) => Promise<T>
      notify: (payload: NadiaNotification) => Promise<boolean>
      requestMicrophoneAccess: () => Promise<boolean>
      readFileDataUrl: (filePath: string) => Promise<string>
      readFileText: (filePath: string) => Promise<NadiaReadFileTextResult>
      selectPaths: (options?: NadiaSelectPathsOptions) => Promise<string[]>
      writeClipboard: (text: string) => Promise<boolean>
      saveImageFromUrl: (url: string) => Promise<boolean>
      saveImageBuffer: (data: ArrayBuffer | Uint8Array, ext: string) => Promise<string>
      saveClipboardImage: () => Promise<string>
      getPathForFile: (file: File) => string
      normalizePreviewTarget: (target: string, baseDir?: string) => Promise<NadiaPreviewTarget | null>
      watchPreviewFile: (url: string) => Promise<NadiaPreviewWatch>
      stopPreviewFileWatch: (id: string) => Promise<boolean>
      setTitleBarTheme?: (payload: NadiaTitleBarTheme) => void
      setNativeTheme?: (mode: 'dark' | 'light' | 'system') => void
      setTranslucency?: (payload: { intensity: number }) => void
      setPreviewShortcutActive?: (active: boolean) => void
      openExternal: (url: string) => Promise<void>
      openPreviewInBrowser?: (url: string) => Promise<void>
      fetchLinkTitle: (url: string) => Promise<string>
      sanitizeWorkspaceCwd: (cwd?: null | string) => Promise<{ cwd: string; sanitized: boolean }>
      settings: {
        getDefaultProjectDir: () => Promise<{ defaultLabel: string; dir: null | string; resolvedCwd: string }>
        pickDefaultProjectDir: () => Promise<{ canceled: boolean; dir: null | string }>
        setDefaultProjectDir: (dir: null | string) => Promise<{ dir: null | string }>
      }
      revealLogs: () => Promise<{ ok: boolean; path: string; error?: string }>
      getRecentLogs: () => Promise<{ path: string; lines: string[] }>
      readDir: (path: string) => Promise<NadiaReadDirResult>
      gitRoot?: (path: string) => Promise<string | null>
      // Reveal a path in the OS file manager (Finder / Explorer).
      revealPath?: (path: string) => Promise<boolean>
      // Rename a file/folder in place (new base name, same parent dir).
      renamePath?: (path: string, newName: string) => Promise<{ path: string }>
      // Write a small UTF-8 text file (hardened path, parent must exist).
      writeTextFile?: (path: string, content: string) => Promise<{ path: string }>
      // Move a file/folder to the OS trash (recoverable).
      trashPath?: (path: string) => Promise<boolean>
      // Git-driven worktree management for the "Start work" flow.
      git?: {
        worktreeList: (repoPath: string) => Promise<NadiaGitWorktree[]>
        worktreeAdd: (
          repoPath: string,
          options?: { name?: string; branch?: string; base?: string; existingBranch?: string }
        ) => Promise<{ path: string; branch: string; repoRoot: string }>
        worktreeRemove: (
          repoPath: string,
          worktreePath: string,
          options?: { force?: boolean }
        ) => Promise<{ removed: string }>
        branchSwitch: (repoPath: string, branch: string) => Promise<{ branch: string }>
        // Local branches for the "convert a branch into a worktree" picker.
        branchList: (repoPath: string) => Promise<NadiaGitBranch[]>
        // Compact working-tree status for the composer coding rail. Null on a
        // non-repo / remote backend (where the Electron probe can't run).
        repoStatus: (repoPath: string) => Promise<NadiaRepoStatus | null>
        // Working-tree-vs-HEAD unified diff for one file (the preview's diff
        // view). Empty string when the file is unchanged or not in a repo.
        fileDiff: (repoPath: string, filePath: string) => Promise<string>
        // Codex-style review pane: changed files per scope, per-file diff, and
        // stage / unstage / revert.
        review: {
          list: (repoPath: string, scope: NadiaReviewScope, baseRef?: null | string) => Promise<NadiaReviewList>
          diff: (
            repoPath: string,
            filePath: string,
            scope: NadiaReviewScope,
            baseRef?: null | string,
            staged?: boolean
          ) => Promise<string>
          stage: (repoPath: string, filePath?: null | string) => Promise<{ ok: boolean }>
          unstage: (repoPath: string, filePath?: null | string) => Promise<{ ok: boolean }>
          revert: (repoPath: string, filePath?: null | string) => Promise<{ ok: boolean }>
          revParse: (repoPath: string, ref?: null | string) => Promise<null | string>
          commit: (repoPath: string, message: string, push: boolean) => Promise<{ ok: boolean }>
          // Diff (staged-or-all) + recent commit subjects for drafting a
          // commit message. Reads only; empty strings off-repo.
          commitContext: (repoPath: string) => Promise<{ diff: string; recent: string }>
          push: (repoPath: string) => Promise<{ ok: boolean }>
          shipInfo: (repoPath: string) => Promise<NadiaReviewShipInfo>
          createPr: (repoPath: string) => Promise<{ url: string }>
        }
        // Repo-first discovery: scan bounded roots for git repos (depth-capped).
        scanRepos: (roots: string[], options?: { maxDepth?: number }) => Promise<{ root: string; label: string }[]>
      }
      terminal: {
        dispose: (id: string) => Promise<boolean>
        onData: (id: string, callback: (payload: string) => void) => () => void
        onExit: (id: string, callback: (payload: NadiaTerminalExit) => void) => () => void
        resize: (id: string, size: { cols: number; rows: number }) => Promise<boolean>
        start: (options?: { cols?: number; cwd?: string; rows?: number }) => Promise<NadiaTerminalSession>
        write: (id: string, data: string) => Promise<boolean>
      }
      onClosePreviewRequested?: (callback: () => void) => () => void
      onOpenUpdatesRequested?: (callback: () => void) => () => void
      onDeepLink?: (
        callback: (payload: { kind: string; name: string; params: Record<string, string> }) => void
      ) => () => void
      signalDeepLinkReady?: () => Promise<{ ok: boolean }>
      onWindowStateChanged?: (callback: (payload: NadiaWindowState) => void) => () => void
      onFocusSession?: (callback: (sessionId: string) => void) => () => void
      onNotificationAction?: (callback: (payload: { actionId: string; sessionId?: string }) => void) => () => void
      onPreviewFileChanged: (callback: (payload: NadiaPreviewFileChanged) => void) => () => void
      onBackendExit: (callback: (payload: BackendExit) => void) => () => void
      onPowerResume?: (callback: () => void) => () => void
      onBootProgress: (callback: (payload: DesktopBootProgress) => void) => () => void
      getBootstrapState: () => Promise<DesktopBootstrapState>
      resetBootstrap: () => Promise<{ ok: boolean }>
      repairBootstrap: () => Promise<{ ok: boolean }>
      cancelBootstrap: () => Promise<{ ok: boolean; cancelled: boolean }>
      onBootstrapEvent: (callback: (payload: DesktopBootstrapEvent) => void) => () => void
      getVersion: () => Promise<DesktopVersionInfo>
      getRemoteDisplayReason?: () => Promise<string | null>
      updates: {
        check: () => Promise<DesktopUpdateStatus>
        apply: (opts?: DesktopUpdateApplyOptions) => Promise<DesktopUpdateApplyResult>
        getBranch: () => Promise<{ branch: string }>
        setBranch: (name: string) => Promise<{ branch: string }>
        onProgress: (callback: (payload: DesktopUpdateProgress) => void) => () => void
      }
      uninstall: {
        summary: () => Promise<DesktopUninstallSummary>
        run: (mode: DesktopUninstallMode) => Promise<DesktopUninstallResult>
      }
      // report the renderer's resolved locale (en/it) so the
      // native menu / About / context menu track the in-app language.
      setMenuLocale?: (locale: string) => void
      // themes.fetchMarketplace/searchMarketplace typing (and
      // the DesktopMarketplace* result types below) removed with the VS Code
      // Marketplace theme-gallery bridge: one NadicodeAI skin, not an
      // operator choice on any surface.
    }
  }
}

export interface NadiaTerminalSession {
  cwd: string
  id: string
  shell: string
}

export interface NadiaTerminalExit {
  code: number | null
  signal: string | null
}

export interface DesktopVersionInfo {
  appVersion: string
  electronVersion: string
  nodeVersion: string
  platform: string
  nadiaRoot: string
}

export type DesktopUninstallMode = 'full' | 'gui' | 'lite'

export interface DesktopUninstallSummary {
  nadia_home: string
  agent_installed: boolean
  gui_installed: boolean
  source_built_artifacts: string[]
  packaged_app_paths: string[]
  userdata_dir: string
  userdata_exists: boolean
  platform: string
  running_app_path?: null | string
  probe?: string
}

export interface DesktopUninstallResult {
  ok: boolean
  mode?: DesktopUninstallMode
  willRemoveAppBundle?: boolean
  scriptPath?: string
  error?: string
  message?: string
}

export interface DesktopUpdateCommit {
  sha: string
  summary: string
  author: string
  at: number
}

export interface DesktopUpdateStatus {
  supported: boolean
  updateAvailable?: boolean
  branch?: string
  currentBranch?: string
  reason?: string
  message?: string
  error?: string
  behind?: number
  currentSha?: string
  targetSha?: string
  commits?: DesktopUpdateCommit[]
  dirty?: boolean
  fetchedAt?: number
}

export type DesktopUpdateDirtyStrategy = 'abort' | 'stash' | 'force'

export interface DesktopUpdateApplyOptions {
  dirtyStrategy?: DesktopUpdateDirtyStrategy
}

export interface DesktopUpdateApplyResult {
  ok: boolean
  branch?: string
  error?: string
  message?: string
  /** True when no staged updater exists (CLI install) and the user should run
   *  `nadia update` themselves. `command` is the exact line to run. */
  manual?: boolean
  command?: string
  nadiaRoot?: string
  /** True when the backend was updated but the GUI couldn't be relaunched in
   *  place (AppImage / dev run): the new version loads on next launch. */
  backendUpdated?: boolean
  /** False when the running GUI package was NOT replaced by this update
   *  (Linux GUI/backend skew, or a sandbox-blocked relaunch). Distinguishes
   *  "backend only" outcomes from a real in-place GUI relaunch. (#45205) */
  guiUpdated?: boolean
  /** True for the Linux GUI/backend-skew terminal state: backend updated but
   *  the running AppImage/.deb/.rpm shell is unchanged and must be
   *  reinstalled. Renders a closeable "update the desktop app" message. */
  guiSkew?: boolean
  /** True when the update finished but the app must be quit + reopened by hand
   *  (e.g. the rebuilt sandbox helper isn't launchable): keep a working
   *  window, don't auto-quit into a dead app. (#45205) */
  manualRestart?: boolean
  /** True when the auto-relaunch was skipped specifically because the rebuilt
   *  chrome-sandbox helper is not launchable (not root:root + setuid). */
  sandboxBlocked?: boolean
  /** True when a detached relauncher took over (macOS bundle swap / Linux
   *  re-exec): the app is about to quit and reopen itself. */
  handedOff?: boolean
}

export type DesktopUpdateStage =
  | 'idle'
  | 'prepare'
  | 'fetch'
  | 'pull'
  | 'pydeps'
  | 'update'
  | 'rebuild'
  | 'restart'
  | 'done'
  | 'manual'
  /** Backend updated but the running GUI package (AppImage/.deb/.rpm) was NOT
   *  changed — the user must update/reinstall the desktop app. Terminal,
   *  closeable; never claims the GUI was updated. (#45205) */
  | 'guiSkew'
  | 'error'

export interface DesktopUpdateProgress {
  stage: DesktopUpdateStage
  message: string
  percent: number | null
  error: string | null
  at: number
}

export interface NadiaConnection {
  baseUrl: string
  isFullscreen: boolean
  mode?: 'local' | 'remote'
  authMode?: 'oauth' | 'token'
  nativeOverlayWidth: number
  source?: 'env' | 'local' | 'settings'
  token: string
  wsUrl: string
  logs: string[]
  // Set for pool (non-primary) backends so the renderer knows which profile a
  // connection belongs to.
  profile?: string
  windowButtonPosition: { x: number; y: number } | null
}

export interface NadiaTitleBarTheme {
  background: string
  foreground: string
}

export interface NadiaWindowState {
  isFullscreen: boolean
  nativeOverlayWidth: number
  windowButtonPosition: { x: number; y: number } | null
}

export interface DesktopActiveProfile {
  // The desktop's stored profile preference, or null when unset (legacy launch
  // that defers to the sticky active_profile / default).
  profile: string | null
}

export interface DesktopConnectionConfig {
  envOverride: boolean
  mode: 'local' | 'remote'
  // The profile this config describes, or null for the global/default
  // connection. Per-profile entries let a profile point at its own backend.
  profile: null | string
  remoteAuthMode: 'oauth' | 'token'
  remoteOauthConnected: boolean
  remoteTokenPreview: string | null
  remoteTokenSet: boolean
  remoteUrl: string
}

export interface DesktopConnectionConfigInput {
  mode: 'local' | 'remote'
  // When set, apply targets this profile's per-profile remote override
  // instead of the global connection.
  // (comment only: was "the save/apply/test targets";
  // save/test were removed with the gateway-settings UI)
  profile?: null | string
  remoteAuthMode?: 'oauth' | 'token'
  remoteToken?: string
  remoteUrl?: string
}

// DesktopConnectionTestResult and DesktopOauthLogoutResult were removed with
// the gateway-settings UI they exclusively served (testConnectionConfig /
// oauthLogoutConnectionConfig above).

export interface DesktopAuthProvider {
  name: string
  displayName: string
  // True when this provider authenticates with a username + password
  // (the gateway's /login page renders a credential form) rather than an
  // OAuth redirect. The session/cookie/ws-ticket machinery is identical;
  // only the login-page form and the desktop's button copy differ.
  supportsPassword?: boolean
}

export interface DesktopConnectionProbeResult {
  baseUrl: string
  reachable: boolean
  authMode: 'oauth' | 'token' | 'unknown'
  providers: DesktopAuthProvider[]
  version: string | null
  error: string | null
}

export interface DesktopOauthLoginResult {
  ok: boolean
  baseUrl: string
  connected: boolean
}

export interface DesktopBootProgress {
  error: string | null
  fakeMode: boolean
  message: string
  phase: string
  progress: number
  running: boolean
  timestamp: number
}

// First-launch install ("bootstrap") event types -- emitted by
// electron/bootstrap-runner.cjs and observed by the renderer install overlay.
// Mirrors the event shapes emitted by runBootstrap()'s onEvent callback.

export interface DesktopBootstrapStageDescriptor {
  name: string
  title?: string
  category?: string
  needs_user_input?: boolean
}

export type DesktopBootstrapStageState = 'pending' | 'running' | 'succeeded' | 'skipped' | 'failed'

export interface DesktopBootstrapStageResult {
  state: DesktopBootstrapStageState
  durationMs: number | null
  startedAt: number | null
  json: { ok: boolean; skipped?: boolean; reason?: string | null; stage: string } | null
  error: string | null
}

export interface DesktopBootstrapUnsupportedPlatform {
  platform: string
  activeRoot: string
  installCommand: string
  docsUrl: string
}

export interface DesktopBootstrapState {
  active: boolean
  manifest: { type: 'manifest'; stages: DesktopBootstrapStageDescriptor[]; protocolVersion: number | null } | null
  stages: Record<string, DesktopBootstrapStageResult>
  error: string | null
  log: Array<{ ts: number; stage: string | null; line: string; stream?: 'stdout' | 'stderr' }>
  startedAt: number | null
  completedAt: number | null
  unsupportedPlatform: DesktopBootstrapUnsupportedPlatform | null
}

export type DesktopBootstrapEvent =
  | { type: 'manifest'; stages: DesktopBootstrapStageDescriptor[]; protocolVersion: number | null }
  | {
      type: 'stage'
      name: string
      state: DesktopBootstrapStageState
      durationMs?: number
      json?: DesktopBootstrapStageResult['json']
      error?: string | null
    }
  | { type: 'log'; stage?: string | null; line: string; stream?: 'stdout' | 'stderr' }
  | { type: 'complete'; marker: Record<string, unknown> }
  | { type: 'failed'; stage?: string | null; error: string }
  | {
      type: 'unsupported-platform'
      platform: string
      activeRoot: string
      installCommand: string
      docsUrl: string
    }

export interface NadiaApiRequest {
  path: string
  method?: string
  body?: unknown
  timeoutMs?: number
  // Route this REST call to a specific profile's backend. Omit for the primary
  // (window) backend. Read-only cross-profile data is served by the primary, so
  // this is only needed for profile-scoped live/settings calls.
  profile?: string | null
}

export interface NadiaNotification {
  title?: string
  body?: string
  silent?: boolean
  kind?: string
  sessionId?: string
  actions?: { id: string; text: string }[]
}

export interface NadiaPreviewTarget {
  binary?: boolean
  byteSize?: number
  kind: 'file' | 'url'
  label: string
  large?: boolean
  language?: string
  mimeType?: string
  path?: string
  previewKind?: 'binary' | 'html' | 'image' | 'text'
  renderMode?: 'preview' | 'source'
  source: string
  url: string
}

export interface NadiaReadFileTextResult {
  binary?: boolean
  byteSize?: number
  language?: string
  mimeType?: string
  path: string
  text: string
  truncated?: boolean
}

export interface NadiaPreviewWatch {
  id: string
  path: string
}

// A real git worktree as reported by `git worktree list` (source of truth for
// the "Start work" flow), as opposed to the session-cwd-derived grouping above.
export interface NadiaGitWorktree {
  path: string
  branch: null | string
  isMain: boolean
  detached: boolean
  locked: boolean
}

// A local branch as offered by the "convert a branch into a worktree" picker.
// `checkedOut` means selecting opens that checkout; `isDefault` means selecting
// switches the main checkout instead of creating `.worktrees/main`.
export interface NadiaGitBranch {
  name: string
  checkedOut: boolean
  isDefault: boolean
  worktreePath: null | string
}

// A single changed path from `git status --porcelain=v2`, classified by state
// so the coding rail / switcher can group + open the right diff.
export interface NadiaRepoStatusFile {
  path: string
  staged: boolean
  unstaged: boolean
  untracked: boolean
  conflicted: boolean
}

// Compact working-tree status for the composer coding rail (parsed from
// `git status --porcelain=v2 --branch`).
export interface NadiaRepoStatus {
  branch: null | string
  // The repo's trunk ("main" / "master" / …), so the UI can offer "branch off
  // the default" from anywhere. Null when no trunk is detected.
  defaultBranch: null | string
  detached: boolean
  ahead: number
  behind: number
  staged: number
  unstaged: number
  untracked: number
  conflicted: number
  // Total distinct changed paths (tracked modified + conflicts + untracked).
  changed: number
  // +/- line counts of tracked changes vs HEAD (staged + unstaged). Untracked
  // files aren't in the diff, so they don't contribute lines.
  added: number
  removed: number
  // Capped changed-file list (REPO_STATUS_FILE_CAP) for the diff/open actions.
  files: NadiaRepoStatusFile[]
}

// Diff scope for the review pane, mirroring Codex: uncommitted working-tree
// changes, all changes vs the branch base, or everything since the current
// turn began.
export type NadiaReviewScope = 'branch' | 'lastTurn' | 'uncommitted'

// One changed file in the review pane (status letter, +/- lines, staged flag).
export interface NadiaReviewFile {
  path: string
  added: number
  removed: number
  // M(odified) A(dded) D(eleted) R(enamed) C(opied) U(nmerged) ?(untracked)
  status: string
  staged: boolean
}

export interface NadiaReviewList {
  files: NadiaReviewFile[]
  // The resolved base ref the scope diffed against (branch merge-base / turn
  // baseline), or null for the uncommitted scope.
  base: null | string
}

// The branch's PR (if any) as reported by `gh pr view`.
export interface NadiaReviewPr {
  url: string
  state: string
  number: number
}

// gh availability/auth + the current branch's PR — drives the review pane's PR
// button (disabled when gh isn't ready, "Open PR" vs "Create PR" otherwise).
export interface NadiaReviewShipInfo {
  ghReady: boolean
  pr: NadiaReviewPr | null
}

export interface NadiaReadDirEntry {
  name: string
  path: string
  isDirectory: boolean
}

export interface NadiaReadDirResult {
  entries: NadiaReadDirEntry[]
  error?: string
}

export interface NadiaPreviewFileChanged {
  id: string
  path: string
  url: string
}

export interface NadiaSelectPathsOptions {
  title?: string
  defaultPath?: string
  directories?: boolean
  multiple?: boolean
  filters?: Array<{ name: string; extensions: string[] }>
}

export interface BackendExit {
  code: number | null
  signal: string | null
}
