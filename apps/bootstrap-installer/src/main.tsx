import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './app.tsx'
import './styles.css'

const systemThemeQuery = '(prefers-color-scheme: dark)'

function applySystemTheme(event?: MediaQueryList | MediaQueryListEvent) {
  const isDark = event?.matches ?? window.matchMedia(systemThemeQuery).matches
  const root = document.documentElement

  root.classList.toggle('dark', isDark)
  root.style.colorScheme = isDark ? 'dark' : 'light'
}

function installSystemThemeListener() {
  const media = window.matchMedia(systemThemeQuery)

  applySystemTheme(media)

  if (media.addEventListener) {
    media.addEventListener('change', applySystemTheme)
    return
  }

  media.addListener?.(applySystemTheme)
}

// System theme mode: the installer imports the desktop stylesheet, whose
// :root/.dark tokens already model light and dark. Apply the OS preference
// before React renders so the first installer frame matches the user's system.
installSystemThemeListener()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
