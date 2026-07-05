import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { I18nProvider } from '@/i18n'

import { ComposerTriggerPopover } from './trigger-popover'

function renderPopover(kind: '@' | '/', loading = false) {
  const onHover = vi.fn()
  const onPick = vi.fn()

  const rendered = render(
    <I18nProvider configClient={null} initialLocale="it">
      <ComposerTriggerPopover
        activeIndex={0}
        items={[]}
        kind={kind}
        loading={loading}
        onHover={onHover}
        onPick={onPick}
      />
    </I18nProvider>
  )

  return { ...rendered, onHover, onPick }
}

describe('ComposerTriggerPopover i18n', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders localized empty lookup copy for @ references', () => {
    const { container } = renderPopover('@')

    expect(screen.getByText('Nessuna corrispondenza.')).toBeTruthy()
    expect(container.textContent).toContain('Prova')
    expect(container.textContent).toContain('@file:')
    expect(container.textContent).toContain('oppure')
    expect(container.textContent).toContain('@folder:')
  })

  it('renders localized loading copy for slash commands', () => {
    renderPopover('/', true)

    // While loading the popover shows only the spinner + loading copy — the
    // `/help` empty-state hint is reserved for the resolved (not-loading) state.
    expect(screen.getByText('Ricerca…')).toBeTruthy()
  })

  it('renders the slash empty-state hint when not loading', () => {
    const { container } = renderPopover('/')

    expect(screen.getByText('Nessuna corrispondenza.')).toBeTruthy()
    expect(container.textContent).toContain('/help')
  })
})
