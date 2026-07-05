import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  Plus,
  RotateCw,
  Trash2,
  Webhook,
  X,
} from "lucide-react";
import { Badge } from "@/nadicodeai-ui-compat";
import { Button } from "@/nadicodeai-ui-compat";
import { Select, SelectOption } from "@/nadicodeai-ui-compat";
import { Spinner } from "@/nadicodeai-ui-compat";
import { H2 } from "@/nadicodeai-ui-compat";
import { api } from "@/lib/api";
import type { WebhookRoute, WebhooksResponse } from "@/lib/api";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { useToast } from "@/nadicodeai-ui-compat";
import { useConfirmDelete } from "@/nadicodeai-ui-compat";
import { useModalBehavior } from "@/hooks/useModalBehavior";
import { Toast } from "@/nadicodeai-ui-compat";
import { Card, CardContent } from "@/nadicodeai-ui-compat";
import { Input } from "@/nadicodeai-ui-compat";
import { Label } from "@/nadicodeai-ui-compat";
import { formatText, useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn, themedBody } from "@/lib/utils";

interface CreatedWebhook {
  url: string;
  secret: string;
}

function CopyButton({ value }: { value: string }) {
  const { t } = useI18n();
  const text = t.webhooks;
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard
      .writeText(value)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {});
  }, [value]);
  return (
    <Button
      ghost
      size="icon"
      title={text.copy}
      aria-label={text.copy}
      onClick={handleCopy}
      className="text-muted-foreground hover:text-foreground"
    >
      {copied ? <Check /> : <Copy />}
    </Button>
  );
}

export default function WebhooksPage() {
  const { t } = useI18n();
  const text = t.webhooks;
  const [data, setData] = useState<WebhooksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [enabling, setEnabling] = useState(false);
  const [restartNeeded, setRestartNeeded] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);
  const [restartError, setRestartError] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const { toast, showToast } = useToast();
  const { setEnd } = usePageHeader();

  // New subscription modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState("");
  const [deliver, setDeliver] = useState("log");
  const [deliverOnly, setDeliverOnly] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreatedWebhook | null>(null);

  const closeCreateModal = useCallback(() => {
    setCreateModalOpen(false);
    setCreated(null);
  }, []);
  const createModalRef = useModalBehavior({
    open: createModalOpen,
    onClose: closeCreateModal,
  });

  const enabled = data?.enabled ?? false;
  const subscriptions = data?.subscriptions ?? [];

  const loadWebhooks = useCallback(() => {
    return api
      .getWebhooks()
      .then(setData)
      .catch(() => showToast(text.loadFailed, "error"))
      .finally(() => setLoading(false));
  }, [showToast, text.loadFailed]);

  useEffect(() => {
    loadWebhooks();
  }, [loadWebhooks]);

  const watchRestartOutcome = useCallback(async () => {
    for (let i = 0; i < 20; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        const st = await api.getActionStatus("gateway-restart", 5);
        if (st.running) continue;
        if (st.exit_code !== 0 && st.exit_code !== null) {
          setRestartMessage(null);
          setRestartNeeded(true);
          setRestartError(formatText(text.restartFailedExitShort, { code: st.exit_code }));
          showToast(
            formatText(text.restartFailedExit, { code: st.exit_code }),
            "error",
          );
        } else {
          setRestartMessage(null);
          setRestartNeeded(false);
          setRestartError(null);
        }
        return;
      } catch {
        // The dashboard may briefly lose its connection while the gateway restarts.
      }
    }
    setRestartMessage(null);
  }, [showToast, text.restartFailedExit, text.restartFailedExitShort]);

  const handleRestart = useCallback(async () => {
    setRestarting(true);
    try {
      await api.restartGateway();
      setRestartNeeded(false);
      setRestartError(null);
      setRestartMessage(text.gatewayRestarting);
      showToast(text.gatewayRestarting, "success");
      setTimeout(() => void loadWebhooks(), 4000);
      void watchRestartOutcome();
    } catch (e) {
      setRestartNeeded(true);
      setRestartError(String(e));
      showToast(formatText(text.failedToRestart, { error: String(e) }), "error");
    } finally {
      setRestarting(false);
    }
  }, [loadWebhooks, showToast, text.failedToRestart, text.gatewayRestarting, watchRestartOutcome]);

  const handleEnableWebhooks = useCallback(async () => {
    setEnabling(true);
    setRestartNeeded(false);
    setRestartError(null);
    try {
      const result = await api.enableWebhooks();
      await loadWebhooks();
      if (result.restart_started) {
        setRestartMessage(text.enabledRestarting);
        showToast(text.enabledRestarting, "success");
        setTimeout(() => void loadWebhooks(), 4000);
        void watchRestartOutcome();
      } else {
        const detail = result.restart_error ? `: ${result.restart_error}` : ".";
        setRestartMessage(null);
        setRestartNeeded(true);
        setRestartError(formatText(text.restartFailed, { detail }));
        showToast(formatText(text.enabledRestartFailed, { detail }), "error");
      }
    } catch (e) {
      showToast(formatText(text.failedToEnable, { error: String(e) }), "error");
    } finally {
      setEnabling(false);
    }
  }, [
    loadWebhooks,
    showToast,
    text.enabledRestartFailed,
    text.enabledRestarting,
    text.failedToEnable,
    text.restartFailed,
    watchRestartOutcome,
  ]);

  const resetForm = useCallback(() => {
    setName("");
    setDescription("");
    setEvents("");
    setDeliver("log");
    setDeliverOnly(false);
    setPrompt("");
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) {
      showToast(text.nameRequired, "error");
      return;
    }
    setCreating(true);
    try {
      const eventsList = events
        .split(",")
        .map((e) => e.trim())
        .filter(Boolean);
      const res = await api.createWebhook({
        name: name.trim(),
        description: description.trim() || undefined,
        events: eventsList.length ? eventsList : undefined,
        deliver,
        deliver_only: deliverOnly,
        prompt: prompt.trim() || undefined,
      });
      showToast(text.created, "success");
      setCreated({ url: res.url, secret: res.secret });
      resetForm();
      loadWebhooks();
    } catch (e) {
      showToast(formatText(text.failedToCreate, { error: String(e) }), "error");
    } finally {
      setCreating(false);
    }
  };

  const [togglingName, setTogglingName] = useState<string | null>(null);

  const handleToggleEnabled = useCallback(
    async (subName: string, nextEnabled: boolean) => {
      setTogglingName(subName);
      try {
        await api.setWebhookEnabled(subName, nextEnabled);
        showToast(
          formatText(nextEnabled ? text.enabledToast : text.disabledToast, { name: subName }),
          "success",
        );
        loadWebhooks();
      } catch (e) {
        showToast(formatText(text.errorWithDetail, { error: String(e) }), "error");
      } finally {
        setTogglingName(null);
      }
    },
    [loadWebhooks, showToast, text.disabledToast, text.enabledToast, text.errorWithDetail],
  );

  const webhookDelete = useConfirmDelete({
    onDelete: useCallback(
      async (name: string) => {
        try {
          await api.deleteWebhook(name);
          showToast(formatText(text.deletedToast, { name }), "success");
          loadWebhooks();
        } catch (e) {
          showToast(formatText(text.errorWithDetail, { error: String(e) }), "error");
          throw e;
        }
      },
      [loadWebhooks, showToast, text.deletedToast, text.errorWithDetail],
    ),
  });

  // Put "New subscription" button in page header
  useLayoutEffect(() => {
    setEnd(
      <Button
        className="uppercase"
        size="sm"
        disabled={!enabled || enabling}
        prefix={<Plus />}
        onClick={() => {
          setCreated(null);
          setCreateModalOpen(true);
        }}
      >
        {text.newSubscription}
      </Button>,
    );
    return () => {
      setEnd(null);
    };
  }, [setEnd, enabled, enabling, loading, text.newSubscription]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  const pendingName = webhookDelete.pendingId ?? "";

  return (
    <div className="flex flex-col gap-6">
      <Toast toast={toast} />

      <DeleteConfirmDialog
        open={webhookDelete.isOpen}
        onCancel={webhookDelete.cancel}
        onConfirm={webhookDelete.confirm}
        title={text.deleteWebhook}
        description={
          pendingName
            ? formatText(text.deleteNamedDescription, { name: pendingName })
            : text.deleteDescription
        }
        loading={webhookDelete.isDeleting}
      />

      {/* Create subscription modal */}
      {createModalOpen && (
        <div
          ref={createModalRef}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-background/85 p-4"
          onClick={(e) => e.target === e.currentTarget && closeCreateModal()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-webhook-title"
        >
          <div className={cn(themedBody, "relative w-full max-w-lg border border-border bg-card shadow-2xl flex flex-col max-h-[90vh] overflow-y-auto")}>
            <Button
              ghost
              size="icon"
              onClick={closeCreateModal}
              className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
              aria-label={text.close}
            >
              <X />
            </Button>

            <header className="p-5 pb-3 border-b border-border">
              <h2
                id="create-webhook-title"
                className="text-display-sm text-base tracking-wider"
              >
                {text.newSubscription}
              </h2>
            </header>

            {created ? (
              <div className="p-5 grid gap-4">
                <p className="text-sm text-muted-foreground">
                  {text.createdHint}
                </p>

                <div className="grid gap-2">
                  <Label>{text.webhookUrl}</Label>
                  <div className="flex items-center gap-2 border border-border bg-background/40 px-3 py-2">
                    <span className="flex-1 min-w-0 truncate font-mono text-xs">
                      {created.url}
                    </span>
                    <CopyButton value={created.url} />
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label>{text.secretShownOnce}</Label>
                  <div className="flex items-center gap-2 border border-warning/40 bg-warning/10 px-3 py-2">
                    <span className="flex-1 min-w-0 truncate font-mono text-xs">
                      {created.secret}
                    </span>
                    <CopyButton value={created.secret} />
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button
                    className="uppercase"
                    size="sm"
                    onClick={closeCreateModal}
                  >
                    {text.done}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="p-5 grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="webhook-name">{text.name}</Label>
                  <Input
                    id="webhook-name"
                    autoFocus
                    placeholder={text.namePlaceholder}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="webhook-description">{text.description}</Label>
                  <Input
                    id="webhook-description"
                    placeholder={text.descriptionPlaceholder}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="webhook-events">{text.events}</Label>
                  <Input
                    id="webhook-events"
                    placeholder={text.eventsPlaceholder}
                    value={events}
                    onChange={(e) => setEvents(e.target.value)}
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="webhook-deliver">{text.deliverTo}</Label>
                    <Select
                      id="webhook-deliver"
                      value={deliver}
                      onValueChange={(v) => setDeliver(v)}
                    >
                      <SelectOption value="log">{text.deliverLog}</SelectOption>
                      <SelectOption value="telegram">{text.deliverTelegram}</SelectOption>
                      <SelectOption value="discord">{text.deliverDiscord}</SelectOption>
                      <SelectOption value="slack">{text.deliverSlack}</SelectOption>
                      <SelectOption value="email">{text.deliverEmail}</SelectOption>
                      <SelectOption value="github_comment">
                        {text.deliverGitHubComment}
                      </SelectOption>
                    </Select>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="webhook-deliver-only">{text.deliverOnly}</Label>
                    <label className="flex items-center gap-2 text-sm text-muted-foreground h-9">
                      <input
                        id="webhook-deliver-only"
                        type="checkbox"
                        checked={deliverOnly}
                        onChange={(e) => setDeliverOnly(e.target.checked)}
                      />
                      {text.skipAgent}
                    </label>
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="webhook-prompt">{text.prompt}</Label>
                  <textarea
                    id="webhook-prompt"
                    className="flex min-h-[80px] w-full border border-border bg-background/40 px-3 py-2 text-sm font-courier shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground/30 focus-visible:border-foreground/25"
                    placeholder={text.promptPlaceholder}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                  />
                </div>

                <div className="flex justify-end">
                  <Button
                    className="uppercase"
                    size="sm"
                    onClick={handleCreate}
                    disabled={creating}
                    prefix={creating ? <Spinner /> : undefined}
                  >
                    {creating ? text.creating : text.create}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {!enabled && (
        <Card className="border-warning/50">
          <CardContent className="flex flex-col gap-4 py-6 text-sm sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Webhook className="h-5 w-5 shrink-0 text-warning" />
              <div className="flex flex-col gap-1">
                <span className="font-medium">{text.receiverDisabled}</span>
                <span className="text-muted-foreground">
                  {text.receiverDisabledDescription}
                </span>
              </div>
            </div>
            <Button
              size="sm"
              className="uppercase shrink-0"
              onClick={handleEnableWebhooks}
              disabled={enabling}
              prefix={enabling ? <Spinner /> : <Webhook className="h-4 w-4" />}
            >
              {enabling ? text.enabling : text.enableWebhooks}
            </Button>
          </CardContent>
        </Card>
      )}

      {restartMessage && !restartNeeded && (
        <Card className="border-border">
          <CardContent className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
            <RotateCw className="h-4 w-4 shrink-0 text-warning" />
            <span>{restartMessage}</span>
          </CardContent>
        </Card>
      )}

      {restartNeeded && (
        <Card className="border-warning/50">
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <span>
                {restartError ??
                  text.restartNeeded}
              </span>
            </div>
            <Button
              size="sm"
              className="uppercase shrink-0"
              onClick={handleRestart}
              disabled={restarting}
              prefix={restarting ? <Spinner /> : <RotateCw className="h-4 w-4" />}
            >
              {restarting ? text.restarting : text.restartGateway}
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        <H2
          variant="sm"
          className="flex items-center gap-2 text-muted-foreground"
        >
          <Webhook className="h-4 w-4" />
          {formatText(text.subscriptions, { count: subscriptions.length })}
        </H2>

        <p className="text-xs text-muted-foreground -mt-1">
          {text.subscriptionsHint}
        </p>

        {subscriptions.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              {text.noSubscriptions}
            </CardContent>
          </Card>
        )}

        {subscriptions.map((sub: WebhookRoute) => (
          <Card key={sub.name}>
            <CardContent className="flex items-start gap-4 py-4">
              <div className={cn("flex-1 min-w-0", !sub.enabled && "opacity-60")}>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="font-medium text-sm truncate">
                    {sub.name}
                  </span>
                  <Badge tone="outline">{sub.deliver}</Badge>
                  {sub.deliver_only && (
                    <Badge tone="secondary">{text.deliverOnlyBadge}</Badge>
                  )}
                  {!sub.enabled && <Badge tone="warning">{text.disabled}</Badge>}
                </div>

                {sub.description && (
                  <p className="text-xs text-muted-foreground mb-2">
                    {sub.description}
                  </p>
                )}

                <div className="flex items-center gap-1 flex-wrap mb-2">
                  {sub.events.length === 0 ? (
                    <Badge tone="secondary">{text.allEvents}</Badge>
                  ) : (
                    sub.events.map((evt) => (
                      <Badge key={evt} tone="secondary">
                        {evt}
                      </Badge>
                    ))
                  )}
                </div>

                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="flex-1 min-w-0 truncate font-mono">
                    {sub.url}
                  </span>
                  <CopyButton value={sub.url} />
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <Button
                  ghost
                  size="sm"
                  className="uppercase"
                  disabled={togglingName === sub.name}
                  onClick={() => handleToggleEnabled(sub.name, !sub.enabled)}
                >
                  {sub.enabled ? text.disable : text.enable}
                </Button>
                <Button
                  ghost
                  destructive
                  size="icon"
                  title={text.delete}
                  aria-label={text.delete}
                  onClick={() => webhookDelete.requestDelete(sub.name)}
                >
                  <Trash2 />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
