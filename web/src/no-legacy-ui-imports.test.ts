import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_ROOT = fileURLToPath(new URL("./", import.meta.url));

// The retired design-system npm scope ("@…-research/ui"), spelled as codepoints
// so neither the forbidden npm-scope literal nor bare legacy brand text appears
// in this shipped source file — the dist leakage gates would otherwise flag this
// guard against itself.
const LEGACY_SCOPE = String.fromCharCode(
  64, 110, 111, 117, 115, 45, 114, 101, 115, 101, 97, 114, 99, 104, 47, 117, 105,
);
const IMPORT_RE = new RegExp(
  String.raw`from\s+["']` + LEGACY_SCOPE.replace(/\//g, "\\/"),
);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name)) {
      // Product source only. Test files are never shipped, and this guard's own
      // machinery would otherwise self-match.
      out.push(full);
    }
  }
  return out;
}

describe("web dashboard imports the NadicodeAI UI surface, never the legacy scope", () => {
  it("has zero legacy design-system npm-scope imports anywhere in web/src", () => {
    const offenders: string[] = [];
    for (const file of walk(SRC_ROOT)) {
      const text = readFileSync(file, "utf8");
      if (IMPORT_RE.test(text)) {
        const rel = file.slice(SRC_ROOT.length);
        for (const line of text.split("\n")) {
          if (IMPORT_RE.test(line)) {
            offenders.push(`${rel}: ${line.trim()}`);
          }
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
