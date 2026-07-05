import { type CSSProperties } from 'react'
import { HackeryButton } from '../components/hackery-button'
import { useI18n } from '../i18n'
import { startInstall } from '../store'

/*
 * Welcome screen.
 *
 * Mirrors the desktop's chat intro (apps/desktop/src/components/chat/intro.tsx):
 *   - NADIA wordmark rendered in Geist, uppercase, tracked
 *   - mix-blend-plus-lighter so the type "glows" on the canvas
 *   - fit-text utility so the wordmark sizes itself to the column
 *
 * No install-path footer. The default install location is correct for
 * 99% of users; the rest will use the CLI installer with a -NadiaHome
 * flag. Showing %LOCALAPPDATA% to grandma is developer-brain.
 */
export default function Welcome() {
  const t = useI18n()
  return (
    <div className="nadia-fade-in flex h-full flex-col items-center justify-center gap-10 px-12 py-10">
      {/* Hero — same recipe the desktop's chat/intro.tsx uses */}
      <div className="w-full max-w-2xl min-w-0 text-center">
        <p
          className="fit-text mx-auto mb-4 w-full font-['Geist'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-midground mix-blend-plus-lighter dark:text-foreground/90"
          style={
            {
              '--fit-text-line-height': '0.9',
              '--fit-text-max': '6rem',
              '--fit-text-min': '2.5rem'
            } as CSSProperties
          }
        >
          <span>
            <span>NADIA</span>
          </span>
          <span aria-hidden="true">NADIA</span>
        </p>

        <p className="m-0 text-center text-base leading-normal tracking-tight text-muted-foreground">
          {t.welcome.tagline}
        </p>
      </div>

      <HackeryButton label={t.welcome.installCta} onClick={() => void startInstall()} />
    </div>
  )
}
