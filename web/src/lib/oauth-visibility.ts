// The NadicodeAI Portal is the sole provider path an operator is offered on the
// web dashboard's environment page. The
// backend /api/providers/oauth catalog still enumerates every OAuth-capable
// provider (it is shared with the CLI/auth universe), so — mirroring the desktop
// provider settings, which filter the same payload down to the portal with
// `providers.find(p => p.id === PORTAL_ID)` — the web OAuth card filters the
// fetched catalog to the portal at render. The portal wire identifier is
// preserved as the provider slug; every visible label reads "NadicodeAI
// Portal".
export const PORTAL_ID = "nous";

/**
 * The provider rows the web env page's OAuth section may render. Given the raw
 * `/api/providers/oauth` catalog, keep only the NadicodeAI Portal — no
 * third-party OAuth login rows reach the served page.
 */
export function portalOnlyOAuthProviders<T extends { id: string }>(
  providers: T[],
): T[] {
  return providers.filter((provider) => provider.id === PORTAL_ID);
}
