const { contextBridge, ipcRenderer, webUtils } = require('electron')

contextBridge.exposeInMainWorld('nadiaDesktop', {
  getConnection: profile => ipcRenderer.invoke('nadia:connection', profile),
  revalidateConnection: () => ipcRenderer.invoke('nadia:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('nadia:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('nadia:gateway:ws-url', profile),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('nadia:window:openSession', sessionId, opts),
  openNewSessionWindow: () => ipcRenderer.invoke('nadia:window:openNewSession'),
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('nadia:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('nadia:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('nadia:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('nadia:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('nadia:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('nadia:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('nadia:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nadia:pet-overlay:state', listener)
      return () => ipcRenderer.removeListener('nadia:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nadia:pet-overlay:control', listener)
      return () => ipcRenderer.removeListener('nadia:pet-overlay:control', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('nadia:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('nadia:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('nadia:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('nadia:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('nadia:connection-config:test', payload),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('nadia:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('nadia:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('nadia:connection-config:oauth-logout', remoteUrl),
  profile: {
    get: () => ipcRenderer.invoke('nadia:profile:get'),
    set: name => ipcRenderer.invoke('nadia:profile:set', name)
  },
  api: request => ipcRenderer.invoke('nadia:api', request),
  notify: payload => ipcRenderer.invoke('nadia:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('nadia:requestMicrophoneAccess'),
  readFileDataUrl: filePath => ipcRenderer.invoke('nadia:readFileDataUrl', filePath),
  readFileText: filePath => ipcRenderer.invoke('nadia:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('nadia:selectPaths', options),
  writeClipboard: text => ipcRenderer.invoke('nadia:writeClipboard', text),
  saveImageFromUrl: url => ipcRenderer.invoke('nadia:saveImageFromUrl', url),
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('nadia:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('nadia:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('nadia:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('nadia:watchPreviewFile', url),
  stopPreviewFileWatch: id => ipcRenderer.invoke('nadia:stopPreviewFileWatch', id),
  setTitleBarTheme: payload => ipcRenderer.send('nadia:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('nadia:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('nadia:translucency', payload),
  setPreviewShortcutActive: active => ipcRenderer.send('nadia:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('nadia:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('nadia:openPreviewInBrowser', url),
  fetchLinkTitle: url => ipcRenderer.invoke('nadia:fetchLinkTitle', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('nadia:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('nadia:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('nadia:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('nadia:setting:defaultProjectDir:pick')
  },
  revealLogs: () => ipcRenderer.invoke('nadia:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('nadia:logs:recent'),
  readDir: dirPath => ipcRenderer.invoke('nadia:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('nadia:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('nadia:fs:reveal', targetPath),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('nadia:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('nadia:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('nadia:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('nadia:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('nadia:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('nadia:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('nadia:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('nadia:git:branchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('nadia:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('nadia:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('nadia:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('nadia:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('nadia:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('nadia:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('nadia:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('nadia:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('nadia:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('nadia:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('nadia:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('nadia:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('nadia:git:review:shipInfo', repoPath),
      createPr: repoPath => ipcRenderer.invoke('nadia:git:review:createPr', repoPath)
    }
  },
  terminal: {
    dispose: id => ipcRenderer.invoke('nadia:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('nadia:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('nadia:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('nadia:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `nadia:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)
      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `nadia:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)
      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('nadia:close-preview-requested', listener)
    return () => ipcRenderer.removeListener('nadia:close-preview-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('nadia:open-updates', listener)
    return () => ipcRenderer.removeListener('nadia:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nadia:deep-link', listener)
    return () => ipcRenderer.removeListener('nadia:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('nadia:deep-link-ready'),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nadia:window-state-changed', listener)
    return () => ipcRenderer.removeListener('nadia:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('nadia:focus-session', listener)
    return () => ipcRenderer.removeListener('nadia:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nadia:notification-action', listener)
    return () => ipcRenderer.removeListener('nadia:notification-action', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nadia:preview-file-changed', listener)
    return () => ipcRenderer.removeListener('nadia:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nadia:backend-exit', listener)
    return () => ipcRenderer.removeListener('nadia:backend-exit', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('nadia:power-resume', listener)
    return () => ipcRenderer.removeListener('nadia:power-resume', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nadia:boot-progress', listener)
    return () => ipcRenderer.removeListener('nadia:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.cjs (apps/desktop/electron/bootstrap-runner.cjs).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('nadia:bootstrap:get'),
  resetBootstrap: () => ipcRenderer.invoke('nadia:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('nadia:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('nadia:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nadia:bootstrap:event', listener)
    return () => ipcRenderer.removeListener('nadia:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('nadia:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('nadia:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('nadia:uninstall:summary'),
    run: mode => ipcRenderer.invoke('nadia:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('nadia:updates:check'),
    apply: opts => ipcRenderer.invoke('nadia:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('nadia:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('nadia:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nadia:updates:progress', listener)
      return () => ipcRenderer.removeListener('nadia:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('nadia:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('nadia:vscode-theme:search', query)
  }
})
