/**
 * Telegram Mini App Utilities
 * Integration helpers for Telegram WebApp API
 */

// Check if running inside Telegram Mini App
export function isTelegramMiniApp(): boolean {
  if (typeof window === 'undefined') return false
  return !!window.Telegram?.WebApp?.initDataUnsafe?.user
}

// Get Telegram WebApp instance
export function getTelegramWebApp() {
  if (typeof window === 'undefined') return null
  return window.Telegram?.WebApp || null
}

// Get current Telegram user data
export function getTelegramUser() {
  const webApp = getTelegramWebApp()
  return webApp?.initDataUnsafe?.user || null
}

// Get Telegram user ID
export function getTelegramUserId(): number | null {
  const user = getTelegramUser()
  return user?.id || null
}

// Get Telegram init data for verification
export function getTelegramInitData(): string | null {
  const webApp = getTelegramWebApp()
  return webApp?.initData || null
}

// Initialize Telegram WebApp (call on app start)
export function initTelegramWebApp() {
  const webApp = getTelegramWebApp()
  if (webApp) {
    webApp.ready()
  }
}

// Show back button
export function showBackButton(callback: () => void) {
  const webApp = getTelegramWebApp()
  if (webApp?.BackButton) {
    webApp.BackButton.onClick(callback)
    webApp.BackButton.show()
  }
}

// Hide back button
export function hideBackButton() {
  const webApp = getTelegramWebApp()
  webApp?.BackButton?.hide()
}

// Show main button
export function showMainButton(text: string, callback: () => void) {
  const webApp = getTelegramWebApp()
  if (webApp?.MainButton) {
    webApp.MainButton.text = text
    webApp.MainButton.onClick(callback)
    webApp.MainButton.show()
  }
}

// Hide main button
export function hideMainButton() {
  const webApp = getTelegramWebApp()
  webApp?.MainButton?.hide()
}

// Close the Mini App
export function closeMiniApp() {
  const webApp = getTelegramWebApp()
  webApp?.close()
}

// Get color scheme (light/dark)
export function getColorScheme(): 'light' | 'dark' {
  const webApp = getTelegramWebApp()
  return (webApp as any)?.colorScheme || 'light'
}

// Get theme parameters
export function getThemeParams() {
  const webApp = getTelegramWebApp()
  return (webApp as any)?.themeParams || {}
}
