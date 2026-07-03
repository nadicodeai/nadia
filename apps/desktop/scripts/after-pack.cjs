/**
 * after-pack.cjs — electron-builder afterPack hook.
 *
 * Stamps the Nadia icon + identity onto the packed Windows Nadia Agent.exe via
 * rcedit (delegated to set-exe-identity.cjs). This runs for EVERY packed build
 * — first install, `nadia desktop`, the installer's --update rebuild, and a
 * dev's manual `npm run pack` — so the branded exe can never silently revert
 * to the stock "Electron" icon/name (the bug when the stamp lived only in
 * install.ps1, which the update path doesn't use).
 *
 * macOS: unsigned release DMGs still need a coherent bundle signature. The
 * Electron binary carries an inherited ad-hoc signature, but the assembled app
 * bundle has no sealed resources. When the app is launched with quarantine,
 * LaunchServices reports it as damaged. If no real signing identity is
 * configured, apply a fresh deep ad-hoc signature to the completed .app before
 * electron-builder creates the DMG/zip. This mirrors the installer/self-update
 * relaunch fixup and is skipped for real signed builds.
 *
 * Windows: rcedit edits PE resources.
 *
 * Best-effort: a cosmetic Windows stamp failure must never fail an otherwise
 * good build, but a macOS ad-hoc signature failure must fail because it creates
 * an unusable customer artifact.
 *
 * electron-builder passes a context with:
 *   - electronPlatformName: 'win32' | 'darwin' | 'linux'
 *   - appOutDir:            the unpacked app directory for this target
 *   - packager.appInfo.productFilename: the exe basename (e.g. 'Nadia')
 */

const path = require('node:path')
const { execFile } = require('node:child_process')

const { stampExeIdentity } = require('./set-exe-identity.cjs')

function run(command, args) {
  return new Promise((resolve, reject) => {
    execFile(command, args, (error, stdout, stderr) => {
      if (error) {
        const detail = stderr?.trim() || stdout?.trim() || error.message
        reject(new Error(`${command} ${args.join(' ')} failed: ${detail}`))
        return
      }
      resolve()
    })
  })
}

function hasRealMacSigningConfig() {
  return Boolean(process.env.CSC_LINK || process.env.APPLE_SIGNING_IDENTITY)
}

async function signMacAppAdHoc(context) {
  const productName = context.packager?.appInfo?.productFilename || 'Nadia'
  const app = path.join(context.appOutDir, `${productName}.app`)

  await run('xattr', ['-cr', app])
  await run('codesign', ['--force', '--deep', '--sign', '-', app])
}

exports.default = async function afterPack(context) {
  if (context.electronPlatformName === 'darwin') {
    if (!hasRealMacSigningConfig()) {
      await signMacAppAdHoc(context)
      console.log('[after-pack] applied macOS deep ad-hoc app signature')
    }
    return
  }

  if (context.electronPlatformName !== 'win32') {
    return
  }

  const productName = context.packager?.appInfo?.productFilename || 'Nadia'
  const exe = path.join(context.appOutDir, `${productName}.exe`)
  const desktopRoot = path.resolve(__dirname, '..')

  try {
    await stampExeIdentity(exe, desktopRoot)
  } catch (err) {
    // Never fail the build over a cosmetic stamp.
    console.warn(`[after-pack] exe identity stamp failed (${err.message}); Nadia Agent.exe keeps the stock Electron icon`)
  }
}
