import { atom } from 'nanostores'

export type CommandPalettePage = 'color-mode' | 'install-theme' | 'theme'

/** Whether the global command palette (Cmd/Ctrl+K) is currently open. */
export const $commandPaletteOpen = atom(false)

/** Optional nested page to open when the palette next opens. */
export const $commandPalettePage = atom<CommandPalettePage | null>(null)

export function openCommandPalette(): void {
  $commandPaletteOpen.set(true)
}

/** Open the palette directly on a nested page. */
export function openCommandPalettePage(page: CommandPalettePage): void {
  $commandPalettePage.set(page)
  $commandPaletteOpen.set(true)
}

export function closeCommandPalette(): void {
  $commandPaletteOpen.set(false)
  $commandPalettePage.set(null)
}

export function setCommandPaletteOpen(open: boolean): void {
  $commandPaletteOpen.set(open)

  if (!open) {
    $commandPalettePage.set(null)
  }
}

export function toggleCommandPalette(): void {
  $commandPaletteOpen.set(!$commandPaletteOpen.get())
}
