import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  isThemeMode,
  themeModes,
  type ThemeMode,
} from "@nadicodeai/ui/lib/theme-mode";

type ResolvedThemeMode = Exclude<ThemeMode, "system">;

interface ThemeModeContextValue {
  mode: ThemeMode;
  resolvedMode: ResolvedThemeMode;
  setMode: (mode: ThemeMode) => void;
}

const STORAGE_KEY = "nadia-dashboard-theme-mode";
const DEFAULT_THEME_MODE: ThemeMode = themeModes.includes("system")
  ? "system"
  : "light";

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null);

function readStoredThemeMode(): ThemeMode {
  if (typeof window === "undefined") return DEFAULT_THEME_MODE;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored && isThemeMode(stored) ? stored : DEFAULT_THEME_MODE;
  } catch {
    return DEFAULT_THEME_MODE;
  }
}

function readSystemMode(): ResolvedThemeMode {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyRootMode(mode: ThemeMode, resolvedMode: ResolvedThemeMode): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("dark", resolvedMode === "dark");
  root.dataset.themeMode = mode;
  root.dataset.resolvedThemeMode = resolvedMode;
  root.style.colorScheme = resolvedMode;
}

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readStoredThemeMode);
  const [systemMode, setSystemMode] =
    useState<ResolvedThemeMode>(readSystemMode);
  const resolvedMode: ResolvedThemeMode = mode === "system" ? systemMode : mode;

  useLayoutEffect(() => {
    applyRootMode(mode, resolvedMode);
  }, [mode, resolvedMode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const syncSystemMode = () => {
      setSystemMode(media.matches ? "dark" : "light");
    };

    syncSystemMode();
    media.addEventListener("change", syncSystemMode);
    return () => media.removeEventListener("change", syncSystemMode);
  }, []);

  const setMode = useCallback((nextMode: ThemeMode) => {
    setModeState(nextMode);
    try {
      window.localStorage.setItem(STORAGE_KEY, nextMode);
    } catch {
      // Storage is optional; the current render still applies the mode.
    }
  }, []);

  const value = useMemo(
    () => ({ mode, resolvedMode, setMode }),
    [mode, resolvedMode, setMode],
  );

  return (
    <ThemeModeContext.Provider value={value}>
      {children}
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode(): ThemeModeContextValue {
  const ctx = useContext(ThemeModeContext);
  if (!ctx) {
    throw new Error("useThemeMode must be used within ThemeModeProvider");
  }
  return ctx;
}
