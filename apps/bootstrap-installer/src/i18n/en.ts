/*
 * English catalog. Brand strings live in the catalog entries below; the
 * welcome/success brand literals ("Install Nadia", "Nadia is ready",
 * "Launch Nadia") are authored here directly.
 */
import type { Catalog } from './types'

export const en: Catalog = {
  welcome: {
    tagline: 'The agent that grows with you. We’ll set things up in the background — takes a few minutes.',
    installCta: 'Install Nadia'
  },
  progress: {
    titleInstall: 'Setting up Nadia Agent',
    titleUpdate: 'Updating Nadia',
    titleDone: 'Done',
    descInstall:
      'This is a one-time setup. The Nadia installer is downloading dependencies and configuring your machine. Subsequent launches will skip this step.',
    descUpdate: 'Nadia is updating to the latest version — this only takes a moment.',
    stepsComplete: (done, total) => `${done} of ${total} steps complete`,
    liveOutput: 'Live output',
    lineCount: (n) => `${n} ${n === 1 ? 'line' : 'lines'}`,
    showDetails: 'Show details',
    hideDetails: 'Hide details',
    cancel: 'Cancel',
    loading: 'Loading…'
  },
  success: {
    ready: 'Nadia is ready',
    launchHintBefore: 'You can launch from here, or any time from your terminal with ',
    launchHintAfter: '.',
    launch: 'Launch Nadia',
    launching: 'Launching',
    launchErrorTitle: 'Couldn’t launch the desktop app',
    launchErrorGeneric: 'The desktop app couldn’t start. See the details below.'
  },
  failure: {
    titleInstall: 'Install didn’t finish',
    titleUpdate: 'Update didn’t finish',
    defaultErrorInstall: 'Something went wrong during installation.',
    defaultErrorUpdate: 'Something went wrong during the update.',
    retryInstall: 'Retry install',
    retryUpdate: 'Retry update',
    openLogs: 'Open logs',
    logLabel: 'Log:'
  },
  causes: {
    alreadyRunning: 'Nadia is still running. Close all Nadia windows and try again.',
    notInstalled: 'Nadia isn’t installed here. Re-run the installer to repair it.',
    rebuild:
      'The desktop app couldn’t be rebuilt. The update was applied — run `nadia desktop` from a terminal to finish it.',
    desktopMissing:
      'The desktop app wasn’t found. The build step may have been skipped — run `nadia desktop` from a terminal.',
    gitMissing: 'Git isn’t installed and couldn’t be installed automatically. Install Git from the link shown above, then try again.',
    download: 'Download failed. Check your internet connection and try again.',
    disk: 'Not enough disk space. Free up some space and try again.',
    permission: 'Not enough permissions. Try again with the access it needs.',
    cancelled: 'Cancelled.'
  },
  errorDetailLabel: 'Details:',
  stages: {
    prerequisites: 'System prerequisites',
    uv: 'Installing uv package manager',
    python: 'Python environment',
    git: 'Installing Git',
    node: 'Node runtime',
    'system-packages': 'System packages',
    repository: 'Cloning the repository',
    repo: 'Cloning the repository',
    venv: 'Creating Python virtual environment',
    dependencies: 'Installing Python dependencies',
    'python-deps': 'Installing Python dependencies',
    'node-deps': 'Installing Node.js dependencies',
    desktop: 'Building the desktop app',
    path: 'Adding Nadia to PATH',
    config: 'Preparing config and skills',
    'config-templates': 'Writing configuration templates',
    'platform-sdks': 'Installing messaging platform SDKs',
    'bootstrap-marker': 'Marking install complete',
    setup: 'Configuring API keys and settings',
    configure: 'Configuring API keys and models',
    gateway: 'Configuring the gateway service',
    complete: 'Finishing install',
    handoff: 'Preparing to update',
    update: 'Downloading the latest version',
    rebuild: 'Rebuilding the desktop app',
    install: 'Installing the update'
  }
}
