'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'

export default function LoginPage() {
  const router = useRouter()
  const { login, isAuthenticated, user, isLoading, isTelegramMiniApp } = useAuth()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Redirect based on user role after authentication
  useEffect(() => {
    if (isAuthenticated && user && !isLoading) {
      // Role is automatically detected from backend response
      // login_type: 1/2 = Student, 3 = Teacher, 4 = Admin
      if (user.login_type === 3 || user.login_type === 4) {
        router.push('/dashboard')
      } else {
        router.push('/student')
      }
    }
  }, [isAuthenticated, user, isLoading, router])

  // Show loading if checking Telegram auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center diamond-gradient">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto rounded-full gold-gradient flex items-center justify-center mb-4 shadow-lg animate-pulse">
            <svg
              className="w-8 h-8 text-white"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <p className="text-[hsl(var(--foreground))] text-lg font-semibold">
            {isTelegramMiniApp ? 'Telegram orqali kirmoqda...' : 'Yuklanmoqda...'}
          </p>
        </div>
      </div>
    )
  }

  // If authenticated, show nothing (will redirect)
  if (isAuthenticated && user) {
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      await login(loginId, password)
      // Redirect is handled by useEffect after successful login
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login yoki parol xato')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center diamond-gradient p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto rounded-full gold-gradient flex items-center justify-center mb-4 shadow-lg">
            <svg
              className="w-8 h-8 text-white"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="text-2xl font-serif font-bold text-[hsl(var(--foreground))]">
            Diamond Education
          </h1>
          <p className="text-[hsl(var(--muted-foreground))] text-sm mt-1">
            Hisobingizga kiring
          </p>
        </div>

        {/* Telegram Mini App Error */}
        {isTelegramMiniApp && !isAuthenticated && (
          <div className="card p-6 shadow-xl mb-6 border-l-4 border-[hsl(var(--primary))]">
            <div className="flex items-start gap-3">
              <svg className="w-6 h-6 text-[hsl(var(--primary))] flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <h3 className="font-semibold text-[hsl(var(--foreground))]">
                  Siz hali botda ro&apos;yxatdan o&apos;tmagansiz
                </h3>
                <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                  Iltimos, avval Telegram botda ro&apos;yxatdan o&apos;ting, keyin bu sahifani qayta oching.
                </p>
                <a
                  href="https://t.me/diamond_education_bot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 mt-3 text-sm font-medium text-[hsl(var(--primary))] hover:underline"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18.717-.962 4.038-1.36 5.36-.168.559-.5.746-.822.765-.696.04-1.225-.46-1.9-.902-.937-.614-1.467-.996-2.377-1.596-1.051-.692-.37-1.073.229-1.695.157-.163 2.876-2.637 2.929-2.863.007-.028.013-.133-.05-.188s-.155-.036-.222-.021c-.095.021-1.61 1.023-4.545 3.003-.43.295-.82.439-1.168.432-.385-.008-1.125-.218-1.676-.397-.674-.22-1.21-.337-1.163-.712.024-.195.291-.395.8-.6 3.14-1.369 5.234-2.271 6.281-2.707 2.992-1.248 3.614-1.465 4.018-1.472.09-.002.288.02.417.123.109.087.139.203.153.29.015.085.033.28.02.433z"/>
                  </svg>
                  Telegram Botga o&apos;tish
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Login Card */}
        <div className="card p-6 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="loginId" className="block text-sm font-medium mb-1.5">
                Login ID
              </label>
              <input
                id="loginId"
                type="text"
                value={loginId}
                onChange={(e) => setLoginId(e.target.value)}
                className="input"
                placeholder="Login ID kiriting"
                required
                disabled={isSubmitting}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1.5">
                Parol
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="Parolingizni kiriting"
                required
                disabled={isSubmitting}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Kirmoqda...
                </span>
              ) : (
                'Kirish'
              )}
            </button>
          </form>

          <div className="mt-4 p-3 rounded-lg bg-[hsl(var(--muted))] text-sm text-[hsl(var(--muted-foreground))]">
            <p className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Rol avtomatik aniqlanadi
            </p>
          </div>
        </div>

        {/* Telegram Link */}
        {!isTelegramMiniApp && (
          <div className="mt-6 text-center">
            <p className="text-[hsl(var(--muted-foreground))] text-sm">
              Telegram orqali kirish uchun{' '}
              <a
                href="https://t.me/diamond_education_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[hsl(var(--secondary))] hover:underline font-medium"
              >
                botdan foydalaning
              </a>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
