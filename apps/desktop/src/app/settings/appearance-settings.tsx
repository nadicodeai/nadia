import { useStore } from '@nanostores/react'

import { LanguageSwitcher } from '@/components/language-switcher'
import { Button } from '@/components/ui/button'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { useI18n } from '@/i18n'
import { Palette } from '@/lib/icons'
import { $embedAllowed, $embedMode, clearEmbedAllowed, type EmbedMode, setEmbedMode } from '@/store/embed-consent'
import { $toolViewMode, setToolViewMode } from '@/store/tool-view'
import { $translucency, setTranslucency } from '@/store/translucency'
import { useTheme } from '@/themes/context'

import { MODE_OPTIONS } from './constants'
import { ListRow, SectionHeading, SettingsContent } from './primitives'

export function AppearanceSettings() {
  const { t, isSavingLocale } = useI18n()
  // One NadicodeAI skin: the only visual choice is the light/dark/system mode.
  const { mode, setMode } = useTheme()
  const toolViewMode = useStore($toolViewMode)
  const embedMode = useStore($embedMode)
  const embedAllowed = useStore($embedAllowed)
  const translucency = useStore($translucency)
  const a = t.settings.appearance

  const modeOptions = MODE_OPTIONS.map(({ id, icon }) => ({ icon, id, label: t.settings.modeOptions[id].label }))

  const toolOptions = [
    { id: 'product', label: a.product },
    { id: 'technical', label: a.technical }
  ] as const

  const embedOptions = [
    { id: 'ask', label: a.embedsAsk },
    { id: 'always', label: a.embedsAlways },
    { id: 'off', label: a.embedsOff }
  ] as const satisfies readonly { id: EmbedMode; label: string }[]

  return (
    <SettingsContent>
      <div>
        <SectionHeading icon={Palette} title={a.title} />
        <p className="max-w-2xl text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
          {a.intro}
        </p>

        <div className="mt-2">
          <ListRow
            action={<LanguageSwitcher />}
            description={isSavingLocale ? t.language.saving : t.language.description}
            title={t.language.label}
          />

          {/* Appearance mode is the single visual choice — no skin gallery. */}
          <ListRow
            action={<SegmentedControl onChange={setMode} options={modeOptions} value={mode} />}
            description={a.colorModeDesc}
            title={a.colorMode}
          />

          <ListRow
            action={
              <div className="flex items-center gap-3">
                <input
                  aria-label={a.translucencyTitle}
                  className="h-1 w-40 cursor-pointer appearance-none rounded-full bg-(--ui-stroke-tertiary)"
                  max={100}
                  min={0}
                  onChange={event => setTranslucency(Number(event.target.value))}
                  step={5}
                  style={{ accentColor: 'var(--dt-primary)' }}
                  type="range"
                  value={translucency}
                />
                <span className="w-9 text-right text-[length:var(--conversation-caption-font-size)] tabular-nums text-(--ui-text-tertiary)">
                  {translucency}%
                </span>
              </div>
            }
            description={a.translucencyDesc}
            title={a.translucencyTitle}
          />

          <ListRow
            action={<SegmentedControl onChange={setToolViewMode} options={toolOptions} value={toolViewMode} />}
            description={a.toolViewDesc}
            title={a.toolViewTitle}
          />

          <ListRow
            action={
              <div className="flex flex-col items-end gap-1.5">
                <SegmentedControl onChange={setEmbedMode} options={embedOptions} value={embedMode} />
                {embedAllowed.length > 0 && (
                  <Button onClick={() => clearEmbedAllowed()} size="inline" variant="text">
                    {a.embedsReset(embedAllowed.length)}
                  </Button>
                )}
              </div>
            }
            description={a.embedsDesc}
            title={a.embedsTitle}
          />
        </div>
      </div>
    </SettingsContent>
  )
}
