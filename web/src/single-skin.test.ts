import { existsSync, readFileSync } from "node:fs";
import { relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC_DIR = fileURLToPath(new URL(".", import.meta.url));

function srcPath(path: string): string {
  return fileURLToPath(new URL(path, import.meta.url));
}

function rel(path: string): string {
  return relative(SRC_DIR, path);
}

describe("single-skin web shell", () => {
  it("does not ship the legacy ThemeSwitcher module", () => {
    expect(existsSync(srcPath("components/ThemeSwitcher.tsx"))).toBe(false);
  });

  it("uses ThemeModeSwitcher as the only dashboard appearance control", () => {
    const appSource = readFileSync(srcPath("App.tsx"), "utf8");
    const mainSource = readFileSync(srcPath("main.tsx"), "utf8");
    const legacyThemeModules = [
      "themes/context.tsx",
      "themes/presets.ts",
      "themes/fonts.ts",
    ]
      .map(srcPath)
      .filter(existsSync)
      .map(rel);

    expect(appSource).toContain("ThemeModeSwitcher");
    expect(appSource).not.toMatch(/\bThemeSwitcher\b/);
    expect(mainSource).toContain("ThemeModeProvider");
    expect(mainSource).not.toMatch(/\bThemeProvider\b/);
    expect(legacyThemeModules).toEqual([]);
  });
});
