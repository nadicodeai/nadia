import { afterEach, describe, expect, it, vi } from "vitest";

import { getInitialLocale, LOCALE_META } from "./context";

function setBrowserLanguages(
  languages: readonly string[],
  language = languages[0] ?? "en-US",
) {
  vi.stubGlobal("navigator", {
    language,
    languages,
  });
}

function setStoredLocale(value: string | null) {
  vi.stubGlobal("localStorage", {
    getItem: vi.fn(() => value),
    setItem: vi.fn(),
  });
}

describe("web i18n context", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("auto-selects Italian for first-run Italian browser locales", () => {
    setStoredLocale(null);
    setBrowserLanguages(["it-IT", "en-US"]);

    expect(getInitialLocale()).toBe("it");
  });

  it("keeps a saved Italian preference", () => {
    setStoredLocale("it");
    setBrowserLanguages(["en-US"]);

    expect(getInitialLocale()).toBe("it");
  });

  it("falls back to English for stale removed saved locales", () => {
    setStoredLocale("zh");
    setBrowserLanguages(["it-IT"]);

    expect(getInitialLocale()).toBe("en");
  });

  it("exposes only English and Italian metadata", () => {
    expect(Object.keys(LOCALE_META)).toEqual(["en", "it"]);
  });
});
