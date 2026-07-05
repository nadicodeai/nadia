import { catalogs, resolveLocale } from '../i18n/index.js'
import { getUiState } from '../app/uiStore.js'

export const PLACEHOLDERS = catalogs.en.placeholders

const PLACEHOLDER_INDEX = Math.floor(Math.random() * PLACEHOLDERS.length)

export const getPlaceholder = () => {
  const locale = resolveLocale(getUiState().locale)

  return catalogs[locale].placeholders[PLACEHOLDER_INDEX] ?? catalogs.en.placeholders[PLACEHOLDER_INDEX]
}
