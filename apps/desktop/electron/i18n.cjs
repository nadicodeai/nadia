'use strict'

const fs = require('node:fs')

// Main-process locale strings for the native app menu, About panel, and
// context menu — the surfaces Electron draws outside the renderer, which the
// renderer's i18n catalog can't reach. Nadia ships exactly English and Italian.
//
// The renderer owns the resolved locale (it reads the stored display.language
// and the system language); it pushes the resolved locale here over IPC so the
// native menu tracks the in-app choice. Before the renderer connects on first
// paint, `detectStartupMenuLocale(app.getLocale())` picks Italian on an Italian
// system and English everywhere else.

const STRINGS = {
  en: {
    menu: {
      about: name => `About ${name}`,
      checkUpdates: 'Check for Updates…',
      file: 'File',
      close: 'Close',
      edit: 'Edit',
      view: 'View',
      actualSize: 'Actual Size',
      zoomIn: 'Zoom In',
      zoomOut: 'Zoom Out',
      window: 'Window',
      help: 'Help'
    },
    context: {
      openImage: 'Open Image',
      copyImage: 'Copy Image',
      copyImageAddress: 'Copy Image Address',
      saveImageAs: 'Save Image As…',
      openLink: 'Open Link',
      copyLink: 'Copy Link',
      addToDictionary: 'Add to dictionary'
    },
    about: { copyright: 'Copyright © 2026 NadicodeAI' }
  },
  it: {
    menu: {
      about: name => `Informazioni su ${name}`,
      checkUpdates: 'Controlla aggiornamenti…',
      file: 'File',
      close: 'Chiudi',
      edit: 'Modifica',
      view: 'Vista',
      actualSize: 'Dimensione effettiva',
      zoomIn: 'Ingrandisci',
      zoomOut: 'Riduci',
      window: 'Finestra',
      help: 'Aiuto'
    },
    context: {
      openImage: 'Apri immagine',
      copyImage: 'Copia immagine',
      copyImageAddress: 'Copia indirizzo immagine',
      saveImageAs: 'Salva immagine con nome…',
      openLink: 'Apri link',
      copyLink: 'Copia link',
      addToDictionary: 'Aggiungi al dizionario'
    },
    about: { copyright: 'Copyright © 2026 NadicodeAI' }
  }
}

// Resolve a BCP-47-ish tag to a supported menu locale, or null. Only English
// and Italian resolve; everything else (including the retired zh/ja) is null
// and falls back to English at the call site.
function normalizeMenuLocale(value) {
  if (typeof value !== 'string') {
    return null
  }

  const key = value.trim().toLowerCase()

  if (!key) {
    return null
  }

  if (key === 'it' || key.startsWith('it-') || key.startsWith('it_')) {
    return 'it'
  }

  if (key === 'en' || key.startsWith('en-') || key.startsWith('en_')) {
    return 'en'
  }

  return null
}

// Startup fallback used before the renderer reports its resolved locale: an
// Italian OS opens the native menu in Italian; everything else in English.
function detectStartupMenuLocale(systemLocale) {
  return normalizeMenuLocale(systemLocale) === 'it' ? 'it' : 'en'
}

function menuStrings(locale) {
  return STRINGS[locale === 'it' ? 'it' : 'en']
}

// Persist the last resolved menu locale so an operator who chose Italian on an
// English Mac gets Italian native menus on the NEXT cold launch — before the
// renderer's IPC push arrives. Only supported locales (en|it) are stored; an
// unsupported value writes null so a later read never resolves to it.
function persistMenuLocale(filePath, locale) {
  try {
    fs.writeFileSync(filePath, JSON.stringify({ locale: normalizeMenuLocale(locale) }), 'utf8')
  } catch {
    // Best-effort: a failed write just means startup falls back to system
    // detection next launch. Never crash the app over a menu preference.
  }
}

// Read the persisted menu locale, or null when the file is missing, unreadable,
// not valid JSON, or holds an unsupported locale. Every failure is silent — the
// caller falls through to system detection.
function readPersistedMenuLocale(filePath) {
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'))

    return normalizeMenuLocale(parsed && parsed.locale)
  } catch {
    return null
  }
}

// Startup precedence: a persisted en|it choice wins; otherwise detect Italian
// from the OS locale; otherwise English.
function resolveStartupMenuLocale(filePath, systemLocale) {
  return readPersistedMenuLocale(filePath) || detectStartupMenuLocale(systemLocale)
}

module.exports = {
  menuStrings,
  normalizeMenuLocale,
  detectStartupMenuLocale,
  persistMenuLocale,
  readPersistedMenuLocale,
  resolveStartupMenuLocale
}
