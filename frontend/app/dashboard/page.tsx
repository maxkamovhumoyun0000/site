'use client'

import { useEffect, useState } from 'react'
import { statsApi, DashboardStats } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'

function StatCard({ 
  title, 
  value, 
  icon, 
  trend 
}: { 
  title: string
  value: string | number
  icon: string
  trend?: { value: number; positive: boolean }
}) {
  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {trend && (
            <p className={`text-xs mt-1 ${trend.positive ? 'text-green-600' : 'text-red-600'}`}>
              {trend.positive ? '+' : ''}{trend.value}% o'tgan haftaga nisbatan
            </p>
          )}
        </div>
        <div className="w-10 h-10 rounded-lg bg-[hsl(var(--primary))] flex items-center justify-center">
          <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
          </svg>
        </div>
      </div>
    </div>
  )
}

function SubjectBreakdown({ data }: { data: { subject: string; count: number }[] }) {
  const total = data.reduce((acc, item) => acc + item.count, 0)
  const colors = {
    English: 'bg-[hsl(var(--primary))]',
    Russian: 'bg-[hsl(var(--secondary))]',
  }

  return (
    <div className="card p-6">
      <h3 className="font-semibold mb-4">Fanlar bo&apos;yicha talabalar</h3>
      <div className="space-y-4">
        {data.map((item) => {
          const percentage = total > 0 ? Math.round((item.count / total) * 100) : 0
          return (
            <div key={item.subject}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span>{item.subject}</span>
                <span className="font-medium">{item.count} ({percentage}%)</span>
              </div>
              <div className="h-2 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                <div
                  className={`h-full ${colors[item.subject as keyof typeof colors] || 'bg-gray-400'} rounded-full transition-all`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function QuickActions() {
  const actions = [
    { label: 'Talaba qo&apos;shish', href: '/dashboard/students?action=add', icon: 'M12 4v16m8-8H4' },
    { label: 'Guruh yaratish', href: '/dashboard/groups?action=add', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' },
    { label: 'Maqola yaratish', href: '/dashboard/articles?action=add', icon: 'M12 4v16m8-8H4' },
    { label: 'D&apos;Coin berish', href: '/dashboard/dcoin?action=award', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  ]

  return (
    <div className="card p-6">
      <h3 className="font-semibold mb-4">Tezkor amallar</h3>
      <div className="grid grid-cols-2 gap-3">
        {actions.map((action) => (
          <a
            key={action.label}
            href={action.href}
            className="flex items-center gap-3 p-3 rounded-lg border border-[hsl(var(--border))] hover:bg-[hsl(var(--muted))] transition-colors"
          >
            <div className="w-8 h-8 rounded-lg bg-[hsl(var(--primary))/0.1] flex items-center justify-center">
              <svg className="w-4 h-4 text-[hsl(var(--primary))]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d={action.icon} />
              </svg>
            </div>
            <span className="text-sm font-medium">{action.label}</span>
          </a>
        ))}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await statsApi.getDashboard()
        setStats(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load stats')
      } finally {
        setIsLoading(false)
      }
    }
    fetchStats()
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-3 border-[hsl(var(--primary))]/30 border-t-[hsl(var(--primary))] rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-6 text-center">
        <p className="text-red-600">{error}</p>
        <button 
          onClick={() => window.location.reload()} 
          className="btn btn-outline mt-4"
        >
          Qayta urinish
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-serif font-bold">Boshqaruv paneli</h1>
        <p className="text-[hsl(var(--muted-foreground))]">
          Xush kelibsiz, {user?.first_name}! Platforma bo&apos;yicha umumiy ko&apos;rsatkichlar.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Umumiy talabalar"
          value={stats?.total_students || 0}
          icon="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
        />
        <StatCard
          title="Faol talabalar"
          value={stats?.active_students || 0}
          icon="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        />
        <StatCard
          title="Guruhlar"
          value={stats?.total_groups || 0}
          icon="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
        />
        <StatCard
          title="Bugungi D'Coin"
          value={stats?.today_dcoins || 0}
          icon="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </div>

      {/* Lower Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SubjectBreakdown data={stats?.subject_breakdown || []} />
        <QuickActions />
      </div>
    </div>
  )
}
