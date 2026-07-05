import { useState } from 'react'
import { type CSSProperties } from 'react'
import { HackeryButton } from '../components/hackery-button'
import { useI18n } from '../i18n'
import { classifyFailure } from '../i18n/failures'
import { launchNadiaDesktop } from '../store'
import { AlertCircle } from 'lucide-react'

/*
 * Success screen. NADIA wordmark stays as the visual anchor
 * (same Geist treatment as Welcome + the desktop chat intro),
 * with a status line below.
 *
 * Launching the desktop can fail (e.g. Stage-Desktop was skipped and
 * Nadia Agent.exe doesn't exist). We catch the Tauri error and surface it
 * inline rather than silently doing nothing — the previous version
 * had `onClick={() => void launchNadiaDesktop()}` which swallowed
 * the rejection and left the user staring at an unresponsive button.
 */
export default function Success() {
  const t = useI18n()
  const [error, setError] = useState<string | null>(null)
  const [launching, setLaunching] = useState(false)

  async function handleLaunch() {
    setError(null)
    setLaunching(true)
    try {
      await launchNadiaDesktop()
      // On success the installer exits — control never returns here.
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      setLaunching(false)
    }
  }

  return (
    <div className="nadia-fade-in flex h-full flex-col items-center justify-center gap-8 px-12 py-10">
      <div className="w-full max-w-2xl min-w-0 text-center">
        <p
          className="fit-text mx-auto mb-4 w-full font-['Geist'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-midground mix-blend-plus-lighter dark:text-foreground/90"
          style={
            {
              '--fit-text-line-height': '0.9',
              '--fit-text-max': '5rem',
              '--fit-text-min': '2.25rem'
            } as CSSProperties
          }
        >
          <span>
            <span>{t.success.ready}</span>
          </span>
          <span aria-hidden="true">{t.success.ready}</span>
        </p>

        <p className="m-0 text-center text-base leading-normal tracking-tight text-muted-foreground">
          {t.success.launchHintBefore}
          <code className="font-mono text-sm text-foreground/80">nadia desktop</code>
          {t.success.launchHintAfter}
        </p>
      </div>

      <HackeryButton
        disabled={launching}
        label={launching ? t.success.launching : t.success.launch}
        loading={launching}
        onClick={() => void handleLaunch()}
      />

      {error && (
        <div role="alert" className="flex max-w-2xl items-start gap-2 text-sm">
          <AlertCircle size={16} className="mt-0.5 shrink-0 text-destructive" />
          <div className="min-w-0">
            {/* Localized headline + plain-language body (known launch class or a
                generic message); the raw diagnostic is demoted to a detail line. */}
            <div className="font-medium text-destructive">{t.success.launchErrorTitle}</div>
            <div className="mt-0.5 text-muted-foreground">
              {(() => {
                const cause = classifyFailure(error)
                return cause ? t.causes[cause] : t.success.launchErrorGeneric
              })()}
            </div>
            <div className="mt-1 text-xs text-muted-foreground/60">
              {t.errorDetailLabel} <span className="font-mono break-words">{error}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
