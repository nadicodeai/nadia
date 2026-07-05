import { t } from '../i18n/index.js'
import { isMac, isRemoteShell } from '../lib/platform.js'

const action = isMac ? 'Cmd' : 'Ctrl'
const paste = isMac ? 'Cmd' : 'Alt'

const copyHotkeys = (): [string, string][] =>
  isMac
    ? [
        ['Cmd+C', t('hotkeys.copySelection')],
        ['Ctrl+C', t('hotkeys.interruptClearDraftExit')]
      ]
    : isRemoteShell()
      ? [
          ['Cmd+C', t('hotkeys.copySelectionWhenForwarded')],
          ['Ctrl+C', t('hotkeys.copySelectionInterruptClearDraftExit')]
        ]
      : [['Ctrl+C', t('hotkeys.copySelectionInterruptClearDraftExit')]]

const buildHotkeys = (): [string, string][] => [
  ...copyHotkeys(),
  [action + '+D', t('hotkeys.exit')],
  [action + '+G / Alt+G', t('hotkeys.openEditor')],
  [action + '+L', t('hotkeys.redraw')],
  [paste + '+V / /paste', t('hotkeys.pasteTextAttachImage')],
  ['Tab', t('hotkeys.applyCompletion')],
  ['↑/↓', t('hotkeys.completionsQueueHistory')],
  ['Ctrl+X', t('hotkeys.openLiveSessionSwitcher')],
  [action + '+A/E', t('hotkeys.homeEndLine')],
  [action + '+Z / ' + action + '+Y', t('hotkeys.undoRedo')],
  [action + '+W', t('hotkeys.deleteWord')],
  [action + '+U/K', t('hotkeys.deleteToStartEnd')],
  [action + '+←/→', t('hotkeys.jumpWord')],
  ['Home/End', t('hotkeys.startEndLine')],
  ['Shift+Enter / Alt+Enter', t('hotkeys.insertNewline')],
  ['\\+Enter', t('hotkeys.multilineContinuation')],
  ['!<cmd>', t('hotkeys.runShellCommand')],
  ['{!<cmd>}', t('hotkeys.interpolateShellOutput')]
]

export const HOTKEYS: [string, string][] = new Proxy([] as [string, string][], {
  get(_target, prop) {
    const hotkeys = buildHotkeys()
    const value = Reflect.get(hotkeys, prop)

    return typeof value === 'function' ? value.bind(hotkeys) : value
  }
})
