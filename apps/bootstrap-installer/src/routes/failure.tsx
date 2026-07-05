import { type CSSProperties } from 'react'
import { useStore } from '@nanostores/react'
import { Button } from '../components/button'
import {
  $logPath,
  $mode,
  openLogDir,
  startInstall,
  startUpdate,
  type BootstrapStateModel
} from '../store'
import { RefreshCw, FileText } from 'lucide-react'
import { useI18n } from '../i18n'
import { classifyFailure } from '../i18n/failures'

interface FailureProps {
  bootstrap: BootstrapStateModel
}

/*
 * Failure screen. Same hero treatment as Welcome/Success — the wordmark
 * carries the brand, so we keep it across every terminal state.
 *
 * The explanation below is localized: known Rust failure classes (see
 * i18n/failures) get a plain-language message in the operator's language;
 * the raw diagnostic is demoted to a secondary detail line — visible for
 * support, but never the headline. Unknown classes fall back to the generic
 * localized message with the raw string as the detail.
 */
export default function Failure({ bootstrap }: FailureProps) {
  const t = useI18n()
  const logPath = useStore($logPath)
  const mode = useStore($mode)
  const isUpdate = mode === 'update'
  const title = isUpdate ? t.failure.titleUpdate : t.failure.titleInstall

  const cause = classifyFailure(bootstrap.error)
  const explanation = cause
    ? t.causes[cause]
    : isUpdate
      ? t.failure.defaultErrorUpdate
      : t.failure.defaultErrorInstall

  return (
    <div className="nadia-fade-in flex h-full flex-col items-center justify-center gap-6 px-12 py-10">
      <div className="w-full max-w-2xl min-w-0 text-center">
        <p
          className="fit-text mx-auto mb-4 w-full font-['Geist'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-destructive mix-blend-plus-lighter dark:text-destructive/90"
          style={
            {
              '--fit-text-line-height': '0.9',
              '--fit-text-max': '5rem',
              '--fit-text-min': '2.25rem'
            } as CSSProperties
          }
        >
          <span>
            <span>{title}</span>
          </span>
          <span aria-hidden="true">{title}</span>
        </p>

        <p className="m-0 mx-auto max-w-xl text-center text-sm leading-normal tracking-tight text-muted-foreground">
          {explanation}
        </p>

        {bootstrap.error && (
          <p className="mx-auto mt-2 max-w-xl text-center text-xs leading-normal text-muted-foreground/60">
            {t.errorDetailLabel}{' '}
            <span className="font-mono break-words">{bootstrap.error}</span>
          </p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={() => void (isUpdate ? startUpdate() : startInstall())} className="gap-1.5">
          <RefreshCw />
          {isUpdate ? t.failure.retryUpdate : t.failure.retryInstall}
        </Button>
        <Button variant="text" onClick={() => void openLogDir()} className="gap-1.5">
          <FileText />
          {t.failure.openLogs}
        </Button>
      </div>

      {logPath && (
        <p className="max-w-lg text-center text-xs text-muted-foreground/70">
          {t.failure.logLabel} <code className="font-mono">{logPath}</code>
        </p>
      )}
    </div>
  )
}
