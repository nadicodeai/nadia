// Provider settings offers exactly one connection: the NadicodeAI Portal.
// Third-party env-configured providers are honored by the runtime but never
// offered here. The card shows the portal
// connection status and an activate / disconnect affordance — nothing else.
import { Button, Card } from '@nadicodeai/ui'
import { useStore } from '@nanostores/react'
import { useCallback, useEffect, useState } from 'react'

import { useI18n } from '@/i18n'
import { Check, KeyRound, Loader2, Trash2 } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { disconnectOAuthProvider, listOAuthProviders } from '@/nadia'
import { notify, notifyError } from '@/store/notifications'
import { $desktopOnboarding, startManualProviderOAuth } from '@/store/onboarding'
import type { OAuthProvider } from '@/types/nadia'

import { SettingsCategoryHeading } from './env-credentials'
import { LoadingState, SettingsContent } from './primitives'

// Wire id stays `nous`; every visible label reads "NadicodeAI Portal".
const PORTAL_ID = 'nous'

// Kept for the settings sidebar contract (settings/index.tsx deep-links this
// view). The legacy 'keys' entry is removed — there is no separate API-keys
// view in a portal-only surface, only the one portal card.
export const PROVIDER_VIEWS = ['accounts'] as const

export type ProviderView = (typeof PROVIDER_VIEWS)[number]

interface ProvidersSettingsProps {
  onClose: () => void
  onViewChange: (view: ProviderView) => void
  view: ProviderView
}

export function ProvidersSettings(_props: ProvidersSettingsProps) {
  const { t } = useI18n()
  const copy = t.settings.providers
  // undefined = still loading; null = fetched, portal not present.
  const [portal, setPortal] = useState<OAuthProvider | null | undefined>(undefined)
  const [disconnecting, setDisconnecting] = useState(false)
  // The onboarding overlay owns the activation flow. Watch its `manual` flag so
  // we re-read the connection status once the user finishes (or dismisses) an
  // activation they launched from this page.
  const onboardingActive = useStore($desktopOnboarding).manual

  const loadPortal = useCallback(async () => {
    const { providers } = await listOAuthProviders()
    setPortal(providers.find(p => p.id === PORTAL_ID) ?? null)
  }, [])

  useEffect(() => {
    let cancelled = false

    void (async () => {
      if (onboardingActive) {
        return
      }

      try {
        const { providers } = await listOAuthProviders()

        if (!cancelled) {
          setPortal(providers.find(p => p.id === PORTAL_ID) ?? null)
        }
      } catch {
        if (!cancelled) {
          setPortal(null)
        }
      }
    })()

    return () => void (cancelled = true)
  }, [onboardingActive])

  async function handleDisconnect(provider: OAuthProvider) {
    if (!window.confirm(copy.removeConfirm(provider.name))) {
      return
    }

    setDisconnecting(true)

    try {
      await disconnectOAuthProvider(provider.id)
      notify({
        durationMs: 3_000,
        kind: 'success',
        title: copy.removedTitle,
        message: copy.removedMessage(provider.name)
      })
      await loadPortal().catch(() => undefined)
    } catch (err) {
      notifyError(err, copy.failedRemove(provider.name))
    } finally {
      setDisconnecting(false)
    }
  }

  if (portal === undefined) {
    return <LoadingState label={copy.loading} />
  }

  const connected = portal?.status?.logged_in ?? false
  const accountLabel = portal?.status?.source_label?.trim() || null
  const name = portal?.name ?? 'NadicodeAI Portal'

  return (
    <SettingsContent>
      <section className="mb-5 grid gap-2">
        <SettingsCategoryHeading icon={KeyRound} title={copy.connectAccount} />
        <p className="-mt-2 mb-1 text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
          {copy.intro}
        </p>
        <Card className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-(--stroke-nadia) p-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-[length:var(--conversation-text-font-size)] font-semibold">{name}</span>
              {connected ? (
                <span className="inline-flex shrink-0 items-center gap-1 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  <Check className="size-3" />
                  {copy.connected}
                </span>
              ) : null}
            </div>
            <p className={cn('mt-1 truncate text-xs leading-5', connected ? 'text-muted-foreground' : 'text-(--ui-text-tertiary)')}>
              {connected ? (accountLabel ?? copy.connected) : copy.notConnected}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {connected ? (
              <Button
                aria-label={`${t.common.remove} ${name}`}
                disabled={disconnecting}
                onClick={() => void handleDisconnect(portal as OAuthProvider)}
                size="icon-sm"
                title={`${t.common.remove} ${name}`}
                variant="ghost"
              >
                {disconnecting ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
              </Button>
            ) : (
              <Button onClick={() => startManualProviderOAuth(PORTAL_ID)} size="sm">
                {t.common.connect}
              </Button>
            )}
          </div>
        </Card>
      </section>
    </SettingsContent>
  )
}
