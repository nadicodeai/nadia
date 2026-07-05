import { describe, expect, it } from "vitest";

import { LOCALE_META } from "./context";
import { en } from "./en";
import { it as italian } from "./it";

const i18nModules = import.meta.glob("./*.ts", { eager: true });

function flattenKeys(value: unknown, prefix = ""): string[] {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return Object.entries(value).flatMap(([key, child]) =>
      flattenKeys(child, prefix ? `${prefix}.${key}` : key),
    );
  }
  return prefix ? [prefix] : [];
}

describe("web i18n locale contract", () => {
  it("exposes exactly English and Italian locale metadata", () => {
    expect(Object.keys(LOCALE_META).sort()).toEqual(["en", "it"]);
  });

  it("ships exactly the English and Italian catalog modules", () => {
    const catalogFiles = Object.keys(i18nModules)
      .filter((file) => !file.endsWith(".test.ts"))
      .filter((file) => !["./index.ts", "./types.ts"].includes(file))
      .map((file) => file.replace(/^\.\//, "").replace(/\.ts$/, ""))
      .sort();

    expect(catalogFiles).toEqual(["en", "it"]);
  });

  it("keeps the Italian catalog structurally complete against English", () => {
    const englishKeys = new Set(flattenKeys(en));
    const italianKeys = new Set(flattenKeys(italian));
    const missing = [...englishKeys].filter((key) => !italianKeys.has(key)).sort();
    const extra = [...italianKeys].filter((key) => !englishKeys.has(key)).sort();

    expect({ missing, extra }).toEqual({ missing: [], extra: [] });
  });
});
