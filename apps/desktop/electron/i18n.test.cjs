'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const {
  menuStrings,
  normalizeMenuLocale,
  detectStartupMenuLocale,
  persistMenuLocale,
  readPersistedMenuLocale,
  resolveStartupMenuLocale
} = require('./i18n.cjs')

function tmpLocalePath() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'nadia-menu-locale-'))
  return path.join(dir, 'menu-locale.json')
}

test('Italian native menu labels match the signed samples', () => {
  const it = menuStrings('it')

  assert.equal(it.menu.edit, 'Modifica')
  assert.equal(it.menu.window, 'Finestra')
  assert.equal(it.menu.help, 'Aiuto')
})

test('English native menu labels are English', () => {
  const en = menuStrings('en')

  assert.equal(en.menu.edit, 'Edit')
  assert.equal(en.menu.window, 'Window')
  assert.equal(en.menu.help, 'Help')
})

test('unknown or missing locales fall back to English strings', () => {
  assert.equal(menuStrings('de').menu.edit, 'Edit')
  assert.equal(menuStrings(undefined).menu.edit, 'Edit')
})

test('About panel copyright carries the NadicodeAI brand, never Nadia', () => {
  for (const locale of ['en', 'it']) {
    const copyright = menuStrings(locale).about.copyright
    assert.ok(copyright.includes('NadicodeAI'), `${locale} copyright should name NadicodeAI`)
    assert.ok(!/Nadia/i.test(copyright), `${locale} copyright must not mention Nadia`)
    assert.ok(!/Nadia/i.test(copyright), `${locale} copyright must not mention Nadia`)
  }
})

test('normalizeMenuLocale recognizes Italian and English tags only', () => {
  assert.equal(normalizeMenuLocale('it'), 'it')
  assert.equal(normalizeMenuLocale('it-IT'), 'it')
  assert.equal(normalizeMenuLocale('IT_IT'), 'it')
  assert.equal(normalizeMenuLocale('en-US'), 'en')
  assert.equal(normalizeMenuLocale('zh-CN'), null)
  assert.equal(normalizeMenuLocale(''), null)
  assert.equal(normalizeMenuLocale(undefined), null)
})

test('an Italian system starts the menu in Italian, others in English', () => {
  assert.equal(detectStartupMenuLocale('it-IT'), 'it')
  assert.equal(detectStartupMenuLocale('en-US'), 'en')
  assert.equal(detectStartupMenuLocale('fr-FR'), 'en')
  assert.equal(detectStartupMenuLocale(undefined), 'en')
})

test('persisted menu locale round-trips through the config file', () => {
  const file = tmpLocalePath()

  persistMenuLocale(file, 'it')
  assert.equal(readPersistedMenuLocale(file), 'it')

  persistMenuLocale(file, 'en')
  assert.equal(readPersistedMenuLocale(file), 'en')
})

test('persisting normalizes and rejects unsupported locales', () => {
  const file = tmpLocalePath()

  persistMenuLocale(file, 'it-IT')
  assert.equal(readPersistedMenuLocale(file), 'it')

  // An unsupported locale must not corrupt the stored value into something the
  // reader would later resolve; it stores nothing usable.
  persistMenuLocale(file, 'zh-CN')
  assert.equal(readPersistedMenuLocale(file), null)
})

test('a missing or corrupt locale file reads as null (silent fallthrough)', () => {
  assert.equal(readPersistedMenuLocale(path.join(os.tmpdir(), 'does-not-exist-menu-locale.json')), null)

  const file = tmpLocalePath()
  fs.writeFileSync(file, '{ not json', 'utf8')
  assert.equal(readPersistedMenuLocale(file), null)

  fs.writeFileSync(file, JSON.stringify({ locale: 'de' }), 'utf8')
  assert.equal(readPersistedMenuLocale(file), null)
})

test('startup precedence: stored Italian wins over an English system', () => {
  const file = tmpLocalePath()
  persistMenuLocale(file, 'it')

  // English Mac, but the operator stored Italian → menu starts Italian.
  assert.equal(resolveStartupMenuLocale(file, 'en-US'), 'it')
})

test('startup precedence: no stored value falls back to system detection', () => {
  const file = tmpLocalePath()

  assert.equal(resolveStartupMenuLocale(file, 'it-IT'), 'it')
  assert.equal(resolveStartupMenuLocale(file, 'en-US'), 'en')
  assert.equal(resolveStartupMenuLocale(file, 'fr-FR'), 'en')
})

test('startup precedence: corrupt stored value falls back to system detection', () => {
  const file = tmpLocalePath()
  fs.writeFileSync(file, 'garbage', 'utf8')

  assert.equal(resolveStartupMenuLocale(file, 'it-IT'), 'it')
  assert.equal(resolveStartupMenuLocale(file, 'en-US'), 'en')
})
