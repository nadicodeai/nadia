import { afterEach, describe, expect, it as test } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import { I18nProvider, messages, type Locale } from './index'
import Welcome from '../routes/welcome'
import Progress from '../routes/progress'
import Success from '../routes/success'
import Failure from '../routes/failure'
import type { BootstrapStateModel } from '../store'

const bootstrap: BootstrapStateModel = {
  status: 'running',
  protocolVersion: 1,
  stages: {},
  stageOrder: [],
  currentStage: null,
  installRoot: null,
  error: null,
  logs: []
}

function renderAt(locale: Locale, node: React.ReactNode) {
  return render(<I18nProvider locale={locale}>{node}</I18nProvider>)
}

afterEach(cleanup)

describe('installer routes render Italian under an Italian OS locale', () => {
  test('welcome CTA', () => {
    renderAt('it', <Welcome />)
    expect(screen.getByText('Installa Nadia')).toBeTruthy()
  })

  test('progress chrome', () => {
    renderAt('it', <Progress bootstrap={bootstrap} />)
    expect(screen.getByText('Configurazione di Nadia Agent')).toBeTruthy()
    expect(screen.getByText('Annulla')).toBeTruthy()
    expect(screen.getByText('0 di 0 passaggi completati')).toBeTruthy()
  })

  test('success screen', () => {
    renderAt('it', <Success />)
    // The headline is rendered twice (visible + aria-hidden glow layer).
    expect(screen.getAllByText('Nadia è pronta').length).toBeGreaterThan(0)
    expect(screen.getByText('Avvia Nadia')).toBeTruthy()
  })

  test('failure screen', () => {
    renderAt('it', <Failure bootstrap={bootstrap} />)
    expect(screen.getAllByText('Installazione non completata').length).toBeGreaterThan(0)
    expect(screen.getByText('Riprova installazione')).toBeTruthy()
    expect(screen.getByText('Apri i log')).toBeTruthy()
  })
})

describe('installer routes render English otherwise', () => {
  test('welcome CTA', () => {
    renderAt('en', <Welcome />)
    expect(screen.getByText('Install Nadia')).toBeTruthy()
  })

  test('failure screen', () => {
    renderAt('en', <Failure bootstrap={bootstrap} />)
    expect(screen.getByText('Retry install')).toBeTruthy()
    expect(screen.getByText('Open logs')).toBeTruthy()
  })
})

describe('failure route explains known Rust diagnostics in the operator language', () => {
  function failWith(error: string): BootstrapStateModel {
    return { ...bootstrap, status: 'failed', error }
  }

  test('a known class (already-running) shows the Italian explanation, not the raw English', () => {
    const raw = 'Nadia is still running. Close all Nadia windows and try the update again.'
    renderAt('it', <Failure bootstrap={failWith(raw)} />)
    // Primary explanation is the localized cause message…
    expect(screen.getByText(messages.it.causes.alreadyRunning)).toBeTruthy()
    // …and the raw diagnostic is still visible, demoted to a detail line.
    expect(screen.getByText(raw)).toBeTruthy()
  })

  test('an unknown class shows the localized generic headline plus the raw detail', () => {
    const raw = 'Segmentation fault at 0xdeadbeef'
    renderAt('it', <Failure bootstrap={failWith(raw)} />)
    expect(screen.getByText(messages.it.failure.defaultErrorInstall)).toBeTruthy()
    expect(screen.getByText(raw)).toBeTruthy()
  })

  test('no error at all falls back to the localized generic message', () => {
    renderAt('it', <Failure bootstrap={{ ...bootstrap, status: 'failed', error: null }} />)
    expect(screen.getByText(messages.it.failure.defaultErrorInstall)).toBeTruthy()
  })
})

describe('success route localizes a launch failure and demotes the raw diagnostic', () => {
  test('a launch rejection shows a localized explanation with the raw error below', async () => {
    renderAt('it', <Success />)
    // Drive the real launch handler (no Tauri backend / no install root → it
    // rejects), exercising the actual catch/setError chain unmocked.
    fireEvent.click(screen.getByText('Avvia Nadia'))
    await waitFor(() => {
      // Localized headline stays the primary line…
      expect(screen.getByText(messages.it.success.launchErrorTitle)).toBeTruthy()
      // …and the raw rejection is demoted to the detail line, still visible.
      expect(screen.getByText('no install root')).toBeTruthy()
    })
  })
})

describe('installer follows the OS language through the real provider (production path)', () => {
  // Guards the default-to-English regression: the provider with NO locale prop
  // must resolve the catalog from navigator.language(s), exactly as production
  // mounts it.
  function withNavigatorLanguages<T>(langs: string[] | null, fn: () => T): T {
    const langDesc = Object.getOwnPropertyDescriptor(navigator, 'languages')
    const singleDesc = Object.getOwnPropertyDescriptor(navigator, 'language')
    if (langs === null) {
      // Restore jsdom's defaults by deleting our overrides.
      if (langDesc?.configurable) delete (navigator as unknown as Record<string, unknown>).languages
      if (singleDesc?.configurable) delete (navigator as unknown as Record<string, unknown>).language
    } else {
      Object.defineProperty(navigator, 'languages', { value: langs, configurable: true })
      Object.defineProperty(navigator, 'language', { value: langs[0], configurable: true })
    }
    try {
      return fn()
    } finally {
      if (langDesc) Object.defineProperty(navigator, 'languages', langDesc)
      else delete (navigator as unknown as Record<string, unknown>).languages
      if (singleDesc) Object.defineProperty(navigator, 'language', singleDesc)
      else delete (navigator as unknown as Record<string, unknown>).language
    }
  }

  test('Italian OS language → Italian strings', () => {
    withNavigatorLanguages(['it-IT', 'en-US'], () => {
      render(
        <I18nProvider>
          <Welcome />
        </I18nProvider>
      )
      expect(screen.getByText('Installa Nadia')).toBeTruthy()
    })
  })

  test('English OS language → English strings (no default-to-English fallback masking a bug)', () => {
    withNavigatorLanguages(['en-US'], () => {
      render(
        <I18nProvider>
          <Welcome />
        </I18nProvider>
      )
      expect(screen.getByText('Install Nadia')).toBeTruthy()
    })
  })
})

describe('installer offers no language picker (follows the OS)', () => {
  const screens: Array<[string, React.ReactNode]> = [
    ['welcome', <Welcome />],
    ['progress', <Progress bootstrap={bootstrap} />],
    ['success', <Success />],
    ['failure', <Failure bootstrap={bootstrap} />]
  ]

  for (const [name, node] of screens) {
    test(`${name} has no select/combobox language control`, () => {
      const { container } = renderAt('it', node)
      expect(container.querySelector('select')).toBeNull()
      expect(container.querySelector('[role="combobox"]')).toBeNull()
      expect(container.querySelector('[role="listbox"]')).toBeNull()
    })
  }
})
