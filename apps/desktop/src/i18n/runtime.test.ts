import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { fieldCopyForSchemaKey } from '@/app/settings/field-copy'

import { TRANSLATIONS } from './catalog'
import { it as italian } from './it'
import { setRuntimeI18nLocale, translateNow } from './runtime'

describe('desktop i18n runtime translator', () => {
  beforeEach(() => {
    setRuntimeI18nLocale('en')
  })

  afterEach(() => {
    setRuntimeI18nLocale('en')
  })

  it('translates string paths for the active runtime locale', () => {
    setRuntimeI18nLocale('it')

    expect(translateNow('boot.ready')).toBe('Nadia Desktop è pronto')
    expect(translateNow('composer.lookupNoMatches')).toBe('Nessuna corrispondenza.')
    expect(translateNow('assistant.tool.statusRecovered')).toBe('Ripristinato')
  })

  it('passes arguments to function translations', () => {
    setRuntimeI18nLocale('it')
    expect(translateNow('notifications.updateReadyMessage', 2)).toBe('2 modifiche disponibili.')
  })

  it('translates settings copy for Italian', () => {
    setRuntimeI18nLocale('it')
    expect(translateNow('common.save')).toBe('Salva')
    expect(translateNow('settings.appearance.title')).toBe('Aspetto')
    expect(translateNow('settings.nav.providers')).toBe('Provider')
  })

  it('keeps translated settings field copy addressable from schema keys', () => {
    const field = ['display', 'show_reasoning'].join('.')

    expect(fieldCopyForSchemaKey(italian.settings.fieldLabels, field)).toBe('Blocchi di ragionamento')
    expect(fieldCopyForSchemaKey(italian.settings.fieldDescriptions, field)).toBe(
      'Mostra il ragionamento quando il backend lo fornisce.'
    )
  })

  it('falls back to English when the active locale cannot resolve a key', () => {
    const boot = TRANSLATIONS.it.boot as { ready?: string }
    const originalReady = boot.ready

    try {
      boot.ready = undefined
      setRuntimeI18nLocale('it')

      expect(translateNow('boot.ready')).toBe('Nadia Desktop is ready')
    } finally {
      boot.ready = originalReady
    }
  })

  it('returns the key when no locale can resolve a path', () => {
    setRuntimeI18nLocale('it')

    expect(translateNow('missing.path')).toBe('missing.path')
  })
})
