import { afterEach, describe, expect, it, vi } from "vitest";

import { SelectOption, SelectItem } from "@/nadicodeai-ui-compat";
import { exposePluginSDK, SDK_CONTRACT_VERSION } from "./registry";

describe("dashboard plugin SDK surface stays intact through the UI migration", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("publishes the load-bearing native-<option> SelectOption to third-party plugins", () => {
    const fakeWindow: Record<string, unknown> = {};
    vi.stubGlobal("window", fakeWindow);

    exposePluginSDK();

    const sdk = (fakeWindow as { __NADIA_PLUGIN_SDK__: {
      sdkVersion: string;
      components: Record<string, unknown>;
    } }).__NADIA_PLUGIN_SDK__;

    expect(sdk.sdkVersion).toBe(SDK_CONTRACT_VERSION);
    // SelectOption/SelectItem wrap a native <option> and must remain the exact
    // barrel export the plugin contract has always shipped (dossier: never break).
    expect(sdk.components.SelectOption).toBeDefined();
    expect(sdk.components.SelectOption).toBe(SelectOption);
    expect(sdk.components.SelectItem).toBeDefined();
    expect(sdk.components.SelectItem).toBe(SelectItem);
    // The rest of the published component surface must still be present.
    for (const name of [
      "Card",
      "Badge",
      "Button",
      "Checkbox",
      "Input",
      "Label",
      "Select",
      "Separator",
      "Tabs",
    ]) {
      expect(typeof sdk.components[name]).toBe("function");
    }
  });
});
