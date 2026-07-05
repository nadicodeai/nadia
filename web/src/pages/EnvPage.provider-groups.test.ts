import { describe, expect, it } from "vitest";

import { PROVIDER_GROUPS, getProviderGroup } from "./EnvPage";

describe("EnvPage provider grouping is portal-only", () => {
  it("offers exactly one provider group, named NadicodeAI Portal", () => {
    expect(PROVIDER_GROUPS.map((g) => g.name)).toEqual(["NadicodeAI Portal"]);
  });

  it("groups the portal credentials under NadicodeAI Portal", () => {
    expect(getProviderGroup("NOUS_API_KEY")).toBe("NadicodeAI Portal");
    expect(getProviderGroup("NOUS_BASE_URL")).toBe("NadicodeAI Portal");
  });

  it("no longer routes third-party provider keys to a named provider group", () => {
    // Post-A the backend payload is portal-only; the page's own grouping table
    // must not resurrect a third-party provider group. Any stray non-portal
    // provider key falls through to the generic "Other" bucket.
    expect(getProviderGroup("ANTHROPIC_API_KEY")).toBe("Other");
    expect(getProviderGroup("OPENROUTER_API_KEY")).toBe("Other");
  });
});
