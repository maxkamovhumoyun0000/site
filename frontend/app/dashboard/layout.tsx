'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { useAuth, getUserRole } from '@/lib/auth-context'

const navItems = [
  { href: '/dashboard', label: "Umumiy ko'rinish", icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
]

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, isLoading, isAuthenticated, logout } = useAuth()
  const [isMobileLayout, setIsMobileLayout] = useState(false)
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [desktopSidebarVisible, setDesktopSidebarVisible] = useState(true)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [isLoading, isAuthenticated, router])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const media = window.matchMedia('(max-width: 1023px)')
    const sync = () => {
      setIsMobileLayout(media.matches)
      if (!media.matches) setMobileDrawerOpen(false)
    }
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    if (!isMobileLayout) {
      document.body.style.overflow = ''
      return
    }
    document.body.style.overflow = mobileDrawerOpen ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [isMobileLayout, mobileDrawerOpen])

  useEffect(() => {
    if (!isMobileLayout || !mobileDrawerOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileDrawerOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isMobileLayout, mobileDrawerOpen])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center diamond-gradient">
        <div className="w-8 h-8 border-3 border-[hsl(var(--primary))/0.24] border-t-[hsl(var(--primary))] rounded-full animate-spin" />
      </div>
    )
  }

  if (!isAuthenticated || !user) {
    return null
  }

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  const sidebarVisible = isMobileLayout ? mobileDrawerOpen : desktopSidebarVisible

  return (
    <div className="min-h-screen bg-[hsl(var(--background))]">
      {isMobileLayout ? (
        <div
          className={`fixed inset-0 z-30 bg-black/40 transition-opacity ${mobileDrawerOpen ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
          onClick={() => setMobileDrawerOpen(false)}
          aria-hidden={!mobileDrawerOpen}
        />
      ) : null}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 z-40 h-screen w-64 premium-gradient border-r border-[hsl(var(--border))] transition-transform duration-300 ${
          sidebarVisible ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex items-center gap-3 p-4 border-b border-[hsl(var(--border))]">
            <div className="w-10 h-10 rounded-lg gold-gradient flex items-center justify-center">
              <svg
                className="w-5 h-5 text-white"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <h1 className="text-[hsl(var(--foreground))] font-serif font-bold">Diamond</h1>
              <p className="text-[hsl(var(--muted-foreground))] text-xs">Admin Panel</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4">
            <ul className="space-y-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => {
                        if (isMobileLayout) setMobileDrawerOpen(false)
                      }}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                        isActive
                          ? 'bg-[hsl(var(--primary))/0.12] text-[hsl(var(--foreground))]'
                          : 'text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--primary))/0.08] hover:text-[hsl(var(--foreground))]'
                      }`}
                    >
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={1.5}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d={item.icon}
                        />
                      </svg>
                      {item.label}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>

          {/* User Info */}
          <div className="p-4 border-t border-[hsl(var(--border))]">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-[hsl(var(--primary))/0.12] flex items-center justify-center text-[hsl(var(--primary))] font-medium">
                {user.first_name?.charAt(0) || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[hsl(var(--foreground))] text-sm font-medium truncate">
                  {user.first_name} {user.last_name}
                </p>
                <p className="text-[hsl(var(--muted-foreground))] text-xs">
                  {getUserRole(user.login_type)}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--primary))/0.08] hover:text-[hsl(var(--foreground))] transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Chiqish
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className={`${!isMobileLayout && desktopSidebarVisible ? 'pl-64' : 'pl-0'} transition-all duration-300`}>
        <header className="sticky top-0 z-20 border-b border-[hsl(var(--border))] bg-[hsl(var(--background))/0.95] backdrop-blur">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] text-[hsl(var(--foreground))] hover:bg-[hsl(var(--primary))/0.08]"
                onClick={() => {
                  if (isMobileLayout) setMobileDrawerOpen((prev) => !prev)
                  else setDesktopSidebarVisible((prev) => !prev)
                }}
                aria-label="Toggle sidebar"
              >
                ☰
              </button>
              <span className="text-sm font-medium text-[hsl(var(--foreground))]">Dashboard</span>
            </div>
            <div className="text-xs text-[hsl(var(--muted-foreground))]">
              {user.first_name} {user.last_name}
            </div>
          </div>
        </header>
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
