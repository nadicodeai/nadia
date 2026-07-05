export { I18nProvider, useI18n, LOCALE_META } from "./context";
export type { Locale, Translations } from "./types";

export function formatText(template: string, values: Record<string, string | number>): string {
  return Object.entries(values).reduce(
    (message, [key, value]) => message.replaceAll(`{${key}}`, String(value)),
    template,
  );
}
