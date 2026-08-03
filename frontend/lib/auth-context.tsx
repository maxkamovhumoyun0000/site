'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { authApi, User, getAuthToken, setAuthToken } from './api'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  isTelegramMiniApp: boolean
  login: (login_id: string, password: string) => Promise<void>
  loginWithTelegram: (telegram_id: number, initData?: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Telegram WebApp type declaration
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string
        initDataUnsafe: {
          user?: {
            id: number
            first_name: string
            last_name?: string
            username?: string
          }
        }
        ready: () => void
        expand: () => void
        close: () => void
        MainButton: {
          text: string
          show: () => void
          hide: () => void
          onClick: (callback: () => void) => void
        }
        BackButton: {
          show: () => void
          hide: () => void
          onClick: (callback: () => void) => void
        }
      }
    }
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isTelegramMiniApp, setIsTelegramMiniApp] = useState(false)

  const refreshUser = async () => {
    try {
      const token = getAuthToken()
      if (!token) {
        setUser(null)
        return
      }
      const userData = await authApi.me()
      setUser(userData)
    } catch (error) {
      setUser(null)
      setAuthToken(null)
    }
  }

  // Check if running in Telegram Mini App
  const checkTelegramMiniApp = (): boolean => {
    if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initDataUnsafe?.user) {
      return true
    }
    return false
  }

  // Auto-login with Telegram ID
  const autoLoginWithTelegram = async () => {
    const tg = window.Telegram?.WebApp
    if (tg?.initDataUnsafe?.user?.id) {
      try {
        tg.ready()
        const response = await authApi.loginWithTelegram(
          tg.initDataUnsafe.user.id,
          tg.initData
        )
        setUser(response.user)
        return true
      } catch (error) {
        // User not registered in bot yet
        return false
      }
    }
    return false
  }

  useEffect(() => {
    const initAuth = async () => {
      // Check if in Telegram Mini App
      const isTgApp = checkTelegramMiniApp()
      setIsTelegramMiniApp(isTgApp)
      
      if (isTgApp) {
        // Try auto-login with Telegram
        const success = await autoLoginWithTelegram()
        if (!success) {
          // If failed, check for existing token
          await refreshUser()
        }
      } else {
        // Normal web flow
        await refreshUser()
      }
      setIsLoading(false)
    }
    initAuth()
  }, [])

  const login = async (login_id: string, password: string) => {
    const tg = window.Telegram?.WebApp
    const telegramId = tg?.initDataUnsafe?.user?.id
    const initData = tg?.initData
    const response = await authApi.login(login_id, password, {
      telegram_id: telegramId,
      init_data: initData,
    })
    setUser(response.user)
  }

  const loginWithTelegram = async (telegram_id: number, initData?: string) => {
    const response = await authApi.loginWithTelegram(telegram_id, initData)
    setUser(response.user)
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isTelegramMiniApp,
        login,
        loginWithTelegram,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Helper function to get user role name
export function getUserRole(login_type: number): string {
  switch (login_type) {
    case 1:
      return 'Student'
    case 2:
      return 'Student'
    case 3:
      return 'Teacher'
    case 4:
      return 'Admin'
    default:
      return 'Unknown'
  }
}

// Check if user is admin or teacher
export function isAdmin(user: User | null): boolean {
  return user?.login_type === 4
}

export function isTeacher(user: User | null): boolean {
  return user?.login_type === 3
}

export function isStudent(user: User | null): boolean {
  return user?.login_type === 1 || user?.login_type === 2
}

export function canManageContent(user: User | null): boolean {
  return user?.login_type === 3 || user?.login_type === 4
}
