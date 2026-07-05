// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { OAuthProvider, OAuthProvidersResponse } from "@/lib/api";

// Guards the CARD RENDER (not just the pure `portalOnlyOAuthProviders`
// filter): the web env page's OAuth section must never surface a
// third-party OAuth login even when the backend catalog carries one, so this
// mocks `api.getOAuthProviders` — the same seam the card calls at render —
// with a multi-provider catalog and asserts on the rendered DOM.
const getOAuthProviders = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getOAuthProviders: () => getOAuthProviders(),
    disconnectOAuthProvider: vi.fn(),
  },
}));

function provider(overrides: Partial<OAuthProvider> = {}): OAuthProvider {
  return {
    id: "nous",
    name: "NadicodeAI Portal",
    flow: "device_code",
    cli_command: "nadia portal connect",
    docs_url: "",
    status: { logged_in: false },
    ...overrides,
  };
}

function multiProviderCatalog(): OAuthProvidersResponse {
  return {
    providers: [
      provider({ id: "nous", name: "NadicodeAI Portal" }),
      provider({
        id: "openai-codex",
        name: "OpenAI Codex",
        flow: "external",
        cli_command: "nadia auth add openai-codex",
      }),
      provider({
        id: "anthropic",
        name: "Anthropic",
        flow: "pkce",
        cli_command: "nadia auth add anthropic",
      }),
      provider({
        id: "xai-oauth",
        name: "xAI",
        flow: "device_code",
        cli_command: "nadia auth add xai-oauth",
      }),
    ],
  };
}

beforeEach(() => {
  getOAuthProviders.mockResolvedValue(multiProviderCatalog());
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("OAuthProvidersCard — portal-only render guard", () => {
  it("renders only the NadicodeAI Portal even though the fetched catalog carries third-party OAuth providers", async () => {
    const { OAuthProvidersCard } = await import("./OAuthProvidersCard");
    const { container } = render(<OAuthProvidersCard />);

    expect(await screen.findByText("NadicodeAI Portal")).toBeTruthy();

    // No third-party OAuth provider name reaches the DOM at all.
    expect(screen.queryByText("OpenAI Codex")).toBeNull();
    expect(screen.queryByText("Anthropic")).toBeNull();
    expect(screen.queryByText("xAI")).toBeNull();

    // Exactly one provider row rendered — the card must drop third parties
    // entirely, not merely reorder or relabel them. Each row is a direct
    // child of the `divide-y` provider list wrapper.
    const rows = container.querySelectorAll(".divide-y.divide-border > div");
    expect(rows).toHaveLength(1);

    // The single rendered login affordance belongs to the portal: with all 4
    // providers logged out, an unfiltered render would show 3 "Login"
    // buttons (portal + anthropic + xai-oauth are non-external; openai-codex
    // is "external" and shows no button while logged out).
    expect(screen.getAllByRole("button", { name: "Login" })).toHaveLength(1);
  });
});
