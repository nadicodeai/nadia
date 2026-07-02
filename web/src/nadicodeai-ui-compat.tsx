/**
 * nadicodeai-ui-compat — legacy web UI compatibility adapter (R15).
 * ==================================================================
 *
 * This is NOT the canonical `@nadicodeai/ui` package (R16). It is a local,
 * surface-owned compatibility barrel that lets the migrated web dashboard keep
 * compiling against the OLD `nous-research/ui` call-site contract while the app
 * moves onto the public `@nadicodeai/ui` surface. Import it as
 * `@/nadicodeai-ui-compat`; never treat it as a shadow Nadia UI package.
 *
 * Old contract it adapts
 * ----------------------
 * (The old package is written here as `nous-research/ui` without its npm `@`
 * scope on purpose: `tools/check_no_nous_npm.py` fails the build on the
 * `@`-scoped literal in any shipped file. Do not re-add the `@`.)
 * Upstream imported concrete primitives and their prop shapes from
 * `nous-research/ui`, including deep paths such as
 * `nous-research/ui/ui/components/select`. Those call sites passed legacy props
 * (`tone`, boolean `ghost/outlined/destructive`, `onCheckedChange`, native
 * `<select>` option children, `mondwest`, ...). This file reconciles those old
 * prop shapes onto the public `@nadicodeai/ui` surface. It does not fabricate
 * unavailable package APIs and does not deep-import `@nadicodeai/ui` internals.
 *
 * Per-export classification (R15 — classify by shape, not by name)
 * ----------------------------------------------------------------
 * (1) MIGRATABLE DUPLICATE — a same-shaped `@nadicodeai/ui` export exists.
 *     Exit: migrate call sites to the package export, then delete the local one.
 *       Spinner                                     -> Spinner
 *       Card/CardHeader/CardContent/CardTitle/
 *         CardDescription                           -> Card family (package superset:
 *                                                      CardFooter, CardAction, ...)
 *       Input                                       -> Input
 *       Label                                       -> Label
 *       Separator                                   -> Separator
 *       Tabs/TabsList/TabsTrigger/TabsContent       -> Tabs family
 *       Dialog/DialogContent/DialogHeader/
 *         DialogTitle/DialogDescription/DialogFooter -> Dialog family (package superset:
 *                                                      DialogClose/Overlay/Portal/Trigger)
 *
 * (2) PROP-SHAPE ADAPTER — a `@nadicodeai/ui` equivalent exists but with an
 *     incompatible contract. Exit: delete when all call sites adopt the native API.
 *       Badge (tone)                                -> Badge / badgeVariants (variant)
 *       Button (ghost/outlined/destructive booleans) -> Button / buttonVariants (variant)
 *       Checkbox (onCheckedChange)                  -> Checkbox
 *       Switch (onCheckedChange)                    -> Switch
 *       Select (native <select>, onValueChange)     -> NativeSelect (NativeSelectOption,
 *                                                      NativeSelectOptGroup)
 *       Segmented/SegmentedOption                   -> ToggleGroup / ToggleGroupItem
 *       ListItem                                    -> Item family (Item, ItemMedia,
 *                                                      ItemContent, ...)
 *       Stats                                       -> StatBlock/StatBlockFigure/
 *                                                      StatBlockLabel + StatsBand
 *       ConfirmDialog                               -> AlertDialog (alert-dialog)
 *       BottomSheet                                 -> Sheet / Drawer
 *       Toast/useToast/ToastState                   -> Toaster (sonner)
 *
 * (3) SURFACE-OWNED LOCAL — no `@nadicodeai/ui` target. No exit path:
 *     surface-owned (R4). Promotion to the package only via R3, never deletion.
 *       Typography         (legacy no-op `mondwest` prop — see below)
 *       H2                 (legacy no-op `mondwest`/`variant` props — see below)
 *       FilterGroup
 *       CopyButton
 *       CommandBlock
 *       useConfirmDelete   (hook)
 *       useBelowBreakpoint (hook)
 *       useGpuTier         (hook)
 *
 * Durable plugin-SDK commitment (NOT a migratable duplicate)
 * ----------------------------------------------------------
 * `SelectOption` and its `SelectItem` alias share a name with package exports
 * but wrap an INCOMPATIBLE native-`<option>` API, so they are not migratable
 * duplicates. They are load-bearing on the `window.__NADIA_PLUGIN_SDK__`
 * global: `web/src/plugins/registry.ts` publishes `SelectOption` on it for
 * third-party plugins. This alias contract MUST NEVER be dropped; it has no
 * exit path.
 *
 * Intentionally-ignored legacy props
 * ----------------------------------
 * `Typography`'s `mondwest` prop and `H2`'s `mondwest`/`variant` props are dead
 * no-ops, kept only so old `nous-research/ui` call sites still type-check. They
 * are deliberately ignored (destructured to `_mondwest`/`_variant`), NOT
 * removed — deleting them would break those call sites.
 */
import * as React from "react";
import { createPortal } from "react-dom";
import { Check, Copy, LoaderCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "outline" | "secondary" | "success" | "warning" | "destructive";

const toneClass: Record<Tone, string> = {
  outline: "border-border bg-transparent text-foreground",
  secondary: "border-transparent bg-muted text-muted-foreground",
  success: "border-transparent bg-success/10 text-success",
  warning: "border-transparent bg-warning/10 text-warning",
  destructive: "border-transparent bg-destructive/10 text-destructive",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "secondary", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 border px-2 py-0.5 text-xs font-medium",
        toneClass[tone] ?? toneClass.secondary,
        className,
      )}
      {...props}
    />
  );
}

export interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "prefix"> {
  destructive?: boolean;
  ghost?: boolean;
  outlined?: boolean;
  prefix?: React.ReactNode;
  suffix?: React.ReactNode;
  size?: "sm" | "icon" | "default" | string;
  variant?: "sm" | "icon" | "default" | string;
}

export function Button({
  children,
  className,
  destructive = false,
  ghost = false,
  outlined = false,
  prefix,
  size,
  suffix,
  type = "button",
  variant,
  ...props
}: ButtonProps) {
  const visualSize = size ?? (variant === "sm" || variant === "icon" || variant === "default" ? variant : undefined);

  return (
    <button
      className={cn(
        "inline-flex min-w-0 items-center justify-center gap-2 border font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        visualSize === "icon" ? "h-8 w-8 p-0" : visualSize === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm",
        ghost
          ? "border-transparent bg-transparent text-foreground hover:bg-muted"
          : outlined
            ? "border-border bg-transparent text-foreground hover:bg-muted"
            : destructive
              ? "border-destructive bg-destructive text-destructive-foreground hover:bg-destructive/90"
              : "border-primary bg-primary text-primary-foreground hover:bg-primary/90",
        className,
      )}
      type={type}
      {...props}
    >
      {prefix}
      {children}
      {suffix}
    </button>
  );
}

export function Spinner({ className, ...props }: React.HTMLAttributes<SVGSVGElement>) {
  return <LoaderCircle className={cn("h-4 w-4 animate-spin", className)} {...props} />;
}

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border border-border bg-card text-card-foreground", className)} {...props} />;
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1.5 p-4", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pt-0", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-display-sm font-semibold tracking-[0.08em]", className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full border border-input bg-background px-3 py-1 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-sm font-medium text-foreground", className)} {...props} />;
}

export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "type"> {
  onCheckedChange?: (checked: boolean) => void;
}

export function Checkbox({ className, onCheckedChange, ...props }: CheckboxProps) {
  return (
    <input
      className={cn("h-4 w-4 accent-primary", className)}
      onChange={(event) => onCheckedChange?.(event.currentTarget.checked)}
      type="checkbox"
      {...props}
    />
  );
}

export interface SwitchProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "type"> {
  onCheckedChange?: (checked: boolean) => void;
}

export function Switch({ className, onCheckedChange, ...props }: SwitchProps) {
  return (
    <input
      className={cn("h-4 w-8 accent-primary", className)}
      onChange={(event) => onCheckedChange?.(event.currentTarget.checked)}
      type="checkbox"
      {...props}
    />
  );
}

export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "onChange"> {
  onValueChange?: (value: string) => void;
  placeholder?: string;
}

export function Select({ className, onValueChange, placeholder: _placeholder, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        "h-9 min-w-0 border border-input bg-background px-3 py-1 text-sm text-foreground outline-none focus:border-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      onChange={(event) => onValueChange?.(event.currentTarget.value)}
      {...props}
    />
  );
}

export function SelectOption(props: React.OptionHTMLAttributes<HTMLOptionElement>) {
  return <option {...props} />;
}

export const SelectItem = SelectOption;

export function Separator({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("h-px w-full bg-border", className)} {...props} />;
}

interface TabsContextValue {
  setValue: (value: string) => void;
  value?: string;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

export interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  value?: string;
}

export function Tabs({
  className,
  defaultValue,
  onValueChange,
  value,
  ...props
}: TabsProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue);
  const selectedValue = value ?? internalValue;
  const context = React.useMemo<TabsContextValue>(
    () => ({
      value: selectedValue,
      setValue: (nextValue) => {
        if (value === undefined) {
          setInternalValue(nextValue);
        }
        onValueChange?.(nextValue);
      },
    }),
    [onValueChange, selectedValue, value],
  );

  return (
    <TabsContext.Provider value={context}>
      <div className={cn("flex flex-col gap-2", className)} {...props} />
    </TabsContext.Provider>
  );
}

export function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("inline-flex items-center gap-1 bg-muted p-1", className)} role="tablist" {...props} />;
}

export function TabsTrigger({
  className,
  disabled,
  onClick,
  value,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { value?: string }) {
  const context = React.useContext(TabsContext);
  const isActive = value !== undefined && context?.value === value;

  return (
    <Button
      aria-selected={isActive}
      className={cn(
        isActive ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
        className,
      )}
      data-state={isActive ? "active" : "inactive"}
      disabled={disabled}
      ghost
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented && !disabled && value !== undefined) {
          context?.setValue(value);
        }
      }}
      role="tab"
      size="sm"
      {...props}
    />
  );
}

export function TabsContent({
  className,
  value,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { value?: string }) {
  const context = React.useContext(TabsContext);
  const isActive = value !== undefined && context?.value === value;

  return (
    <div
      className={cn("outline-none", className)}
      data-state={isActive ? "active" : "inactive"}
      role="tabpanel"
      {...props}
      hidden={!isActive}
    />
  );
}

export interface SegmentedOption<T extends string = string> {
  label: React.ReactNode;
  value: T;
}

export interface SegmentedProps<T extends string = string>
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange"> {
  onChange: (value: T) => void;
  options: SegmentedOption<T>[];
  size?: string;
  value: T;
}

export function Segmented<T extends string = string>({
  className,
  onChange,
  options,
  size: _size,
  value,
  ...props
}: SegmentedProps<T>) {
  return (
    <div className={cn("inline-flex items-center gap-1", className)} {...props}>
      {options.map((option) => (
        <button
          aria-pressed={option.value === value}
          className={cn(
            "border border-border px-2.5 py-1 text-xs font-medium transition-colors",
            option.value === value
              ? "bg-primary text-primary-foreground"
              : "bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
          key={option.value}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function FilterGroup({
  children,
  className,
  label,
}: React.HTMLAttributes<HTMLDivElement> & { label: React.ReactNode }) {
  return (
    <div className={className}>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}

export interface ListItemProps extends React.HTMLAttributes<HTMLDivElement> {
  active?: boolean;
  disabled?: boolean;
}

export function ListItem({
  active = false,
  "aria-disabled": ariaDisabled,
  className,
  disabled = false,
  onClick,
  onKeyDown,
  ...props
}: ListItemProps) {
  const isDisabled = disabled || ariaDisabled === true || ariaDisabled === "true";

  const handleKeyDown =
    onClick || onKeyDown
      ? (event: React.KeyboardEvent<HTMLDivElement>) => {
          onKeyDown?.(event);
          if (!onClick || isDisabled || event.defaultPrevented) {
            return;
          }
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            event.currentTarget.click();
          }
        }
      : undefined;

  return (
    <div
      className={cn(
        "flex min-w-0 cursor-pointer items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-muted",
        active && "bg-primary/10 text-primary",
        className,
      )}
      role={onClick ? "button" : undefined}
      tabIndex={onClick && !isDisabled ? 0 : undefined}
      {...props}
      aria-disabled={onClick && isDisabled ? true : ariaDisabled}
      onClick={isDisabled ? undefined : onClick}
      onKeyDown={handleKeyDown}
    />
  );
}

const DialogContext = React.createContext<{ onOpenChange?: (open: boolean) => void } | null>(null);
const DIALOG_FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function getDialogFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(DIALOG_FOCUSABLE_SELECTOR)).filter(
    (element) => !element.hasAttribute("disabled") && element.getAttribute("aria-hidden") !== "true",
  );
}

export function Dialog({
  children,
  onOpenChange,
  open,
}: {
  children: React.ReactNode;
  onOpenChange?: (open: boolean) => void;
  open: boolean;
}) {
  const value = React.useMemo(() => ({ onOpenChange }), [onOpenChange]);
  if (!open) return null;
  return <DialogContext.Provider value={value}>{children}</DialogContext.Provider>;
}

export function DialogContent({
  className,
  children,
  role,
  tabIndex,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const context = React.useContext(DialogContext);
  const contentRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const content = contentRef.current;
    if (!content) return;

    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const firstFocusable = getDialogFocusable(content)[0] ?? content;
    firstFocusable.focus({ preventScroll: true });

    function handleKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented) return;

      if (event.key === "Escape") {
        event.preventDefault();
        context?.onOpenChange?.(false);
        return;
      }

      if (event.key !== "Tab" || !contentRef.current) return;

      const focusable = getDialogFocusable(contentRef.current);
      if (focusable.length === 0) {
        event.preventDefault();
        contentRef.current.focus({ preventScroll: true });
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || !contentRef.current.contains(active))) {
        event.preventDefault();
        last.focus({ preventScroll: true });
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus({ preventScroll: true });
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus({ preventScroll: true });
    };
  }, [context]);

  return createPortal(
    <div
      className="fixed inset-0 z-[220] flex items-center justify-center bg-background/85 p-4 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) context?.onOpenChange?.(false);
      }}
    >
      <div
        aria-modal="true"
        className={cn("max-h-[90vh] w-full max-w-2xl overflow-auto border border-border bg-card p-4 shadow-xl", className)}
        ref={contentRef}
        role={role ?? "dialog"}
        tabIndex={tabIndex ?? -1}
        {...props}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mb-4 flex flex-col gap-1.5", className)} {...props} />;
}

export function DialogTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-display-sm font-semibold tracking-[0.08em]", className)} {...props} />;
}

export function DialogDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-4 flex justify-end gap-2", className)} {...props} />;
}

export interface ConfirmDialogProps {
  cancelLabel?: string;
  confirmLabel?: string;
  description?: React.ReactNode;
  destructive?: boolean;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  title: React.ReactNode;
}

export function ConfirmDialog({
  cancelLabel = "Cancel",
  confirmLabel = "Confirm",
  description,
  destructive = false,
  loading = false,
  onCancel,
  onConfirm,
  open,
  title,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <DialogFooter>
          <Button outlined onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button destructive={destructive} onClick={onConfirm} disabled={loading}>
            {loading ? "..." : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function BottomSheet({
  children,
  onClose,
  open,
  title,
}: {
  backdropDismissLabel?: string;
  children: React.ReactNode;
  onClose: () => void;
  open: boolean;
  title?: React.ReactNode;
}) {
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[220] flex items-end bg-background/75" onClick={onClose}>
      <div
        className="max-h-[80vh] w-full overflow-auto border-t border-border bg-card p-4 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="text-display-sm font-semibold">{title}</h2>}
          <Button ghost size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function Typography({
  className,
  children,
  mondwest: _mondwest,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { mondwest?: boolean }) {
  return (
    <span className={className} {...props}>
      {children}
    </span>
  );
}

export function H2({
  className,
  mondwest: _mondwest,
  variant: _variant,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement> & { mondwest?: boolean; variant?: string }) {
  return <h2 className={cn("text-display-sm font-semibold tracking-[0.08em]", className)} {...props} />;
}

export interface ToastState {
  id?: number;
  kind?: "success" | "error";
  message: string;
  type?: "success" | "error";
}

export function useToast() {
  const [toast, setToast] = React.useState<ToastState | null>(null);
  const showToast = React.useCallback((message: string, kind: "success" | "error" = "success") => {
    const next = { id: Date.now(), kind, message };
    setToast(next);
    window.setTimeout(() => setToast((current) => (current?.id === next.id ? null : current)), 4200);
  }, []);
  return { toast, showToast };
}

export function Toast({ toast }: { toast: ToastState | null }) {
  if (!toast) return null;
  const kind = toast.kind ?? toast.type ?? "success";
  return (
    <div
      className={cn(
        "fixed right-4 top-4 z-[240] max-w-sm border px-3 py-2 text-sm shadow-lg",
        kind === "error"
          ? "border-destructive bg-destructive text-destructive-foreground"
          : "border-primary bg-primary text-primary-foreground",
      )}
      role="status"
    >
      {toast.message}
    </div>
  );
}

export function useConfirmDelete<T = string>({
  onConfirm,
  onDelete,
}: {
  onConfirm?: (id: T) => void | Promise<void>;
  onDelete?: (id: T) => void | Promise<void>;
}) {
  const [pendingId, setPendingId] = React.useState<T | null>(null);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const requestDelete = React.useCallback((id: T) => setPendingId(id), []);
  const cancel = React.useCallback(() => setPendingId(null), []);
  const confirm = React.useCallback(async () => {
    if (pendingId == null) return;
    const handler = onDelete ?? onConfirm;
    if (!handler) {
      setPendingId(null);
      return;
    }
    setIsDeleting(true);
    try {
      await handler(pendingId);
      setPendingId(null);
    } finally {
      setIsDeleting(false);
    }
  }, [onConfirm, onDelete, pendingId]);
  return { pendingId, isOpen: pendingId != null, isDeleting, requestDelete, cancel, confirm };
}

export function useBelowBreakpoint(px: number) {
  const query = `(max-width: ${px - 1}px)`;
  const [matches, setMatches] = React.useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  );

  React.useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

export function useGpuTier() {
  const [tier, setTier] = React.useState(1);
  React.useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setTier(0);
      return;
    }
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    setTier(gl ? 1 : 0);
  }, []);
  return tier;
}

export function CopyButton({
  copiedLabel = "Copied",
  label = "Copy",
  text,
  value,
}: {
  copiedLabel?: string;
  label?: string;
  text?: string;
  value?: string;
}) {
  const [copied, setCopied] = React.useState(false);
  const content = text ?? value ?? "";
  return (
    <Button
      ghost
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(content);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      }}
      prefix={copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    >
      {copied ? copiedLabel : label}
    </Button>
  );
}

export function CommandBlock({
  code,
  label,
}: {
  code?: string | null;
  label?: React.ReactNode;
}) {
  if (!code) return null;
  return (
    <div className="space-y-2 border border-border bg-muted/30 p-3">
      {label && <div className="text-xs font-medium text-muted-foreground">{label}</div>}
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate font-mono text-xs">{code}</code>
        <CopyButton value={code} />
      </div>
    </div>
  );
}

export function Stats({
  className,
  items,
}: {
  className?: string;
  items: Array<{ label: React.ReactNode; value: React.ReactNode }>;
}) {
  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {items.map((item, index) => (
        <div className="min-w-0 border border-border bg-muted/20 p-3" key={index}>
          <div className="truncate text-xs text-muted-foreground">{item.label}</div>
          <div className="truncate text-lg font-semibold text-foreground">{item.value}</div>
        </div>
      ))}
    </div>
  );
}
