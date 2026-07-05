import type { PanelSection } from '../types.js'
import { t } from '../i18n/index.js'

export const getSetupRequiredTitle = () => t('setup.title')

export const buildSetupRequiredSections = (): PanelSection[] => [
  {
    text: t('setup.body')
  },
  {
    rows: [
      ['/model', t('setup.modelAction')],
      ['/setup', t('setup.setupAction')],
      ['Ctrl+C', t('setup.exitAction')]
    ],
    title: t('setup.actionsTitle')
  }
]
