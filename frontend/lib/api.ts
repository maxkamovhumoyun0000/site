/**
 * Diamond Education API Client
 * Connects to FastAPI backend at /api
 */

const API_BASE =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL?.trim())
    ? process.env.NEXT_PUBLIC_API_BASE_URL!.trim()
    : 'http://localhost:3001'

// Token management
let authToken: string | null = null

export function setAuthToken(token: string | null) {
  authToken = token
  if (token) {
    localStorage.setItem('diamond_token', token)
  } else {
    localStorage.removeItem('diamond_token')
  }
}

export function getAuthToken(): string | null {
  if (authToken) return authToken
  if (typeof window !== 'undefined') {
    authToken = localStorage.getItem('diamond_token')
  }
  return authToken
}

// Base fetch wrapper
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken()
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  const response = await fetch(`${API_BASE}${cleanEndpoint}`, {
    ...options,
    headers,
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `API Error: ${response.status}`)
  }
  
  return response.json()
}

// ============== Types ==============
export interface User {
  id: number
  login_id: string
  first_name: string
  last_name: string
  phone?: string
  subject: string
  login_type: number
  level?: string
  access_enabled: boolean
  language?: string
  dcoin_balance: number
  created_at?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Article {
  id: number
  title: string
  content: string
  subject: string
  level?: string
  author_id: number
  is_published: boolean
  visible_to_teachers: boolean
  visible_to_support_teachers: boolean
  visible_to_students: boolean
  created_at?: string
}

export interface Group {
  id: number
  name: string
  teacher_id?: number
  level?: string
  student_count: number
  created_at?: string
}

export interface Message {
  id: number
  sender_id: number
  recipient_id: number
  subject: string
  content: string
  is_read: boolean
  created_at: string
  sender_name?: string
  sender_last_name?: string
  recipient_name?: string
  recipient_last_name?: string
}

export interface DCoinTransaction {
  id: number
  student_id: number
  amount: number
  transaction_type: string
  reason: string
  created_at: string
  first_name?: string
  last_name?: string
  login_id?: string
}

export interface VocabularyWord {
  id: number
  word: string
  subject: string
  language: string
  level?: string
  translation_uz?: string
  translation_ru?: string
  definition?: string
  example?: string
}

export interface DashboardStats {
  total_students: number
  active_students: number
  total_groups: number
  total_articles: number
  today_dcoins: number
  subject_breakdown: { subject: string; count: number }[]
}

export interface LeaderboardEntry {
  id: number
  first_name: string
  last_name: string
  login_id: string
  level?: string
  subject: string
  total_dcoins: number
}

// ============== Auth API ==============
export const authApi = {
  login: async (
    login_id: string,
    password: string,
    extra?: { telegram_id?: number; init_data?: string; device_id?: string }
  ): Promise<LoginResponse> => {
    const response = await apiFetch<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        login_id,
        password,
        telegram_id: extra?.telegram_id,
        init_data: extra?.init_data,
        device_id: extra?.device_id,
      }),
    })
    setAuthToken(response.access_token)
    return response
  },
  
  // Telegram Mini App authentication
  loginWithTelegram: async (telegram_id: number, initData?: string): Promise<LoginResponse> => {
    const response = await apiFetch<LoginResponse>('/auth/telegram', {
      method: 'POST',
      body: JSON.stringify({ telegram_id, init_data: initData }),
    })
    setAuthToken(response.access_token)
    return response
  },
  
  register: async (data: {
    login_id: string
    password: string
    first_name: string
    last_name: string
    phone?: string
    subject?: string
    level?: string
    login_type?: number
  }): Promise<LoginResponse> => {
    const response = await apiFetch<LoginResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
    setAuthToken(response.access_token)
    return response
  },
  
  me: async (): Promise<User> => {
    return apiFetch<User>('/auth/me')
  },
  
  logout: async (): Promise<void> => {
    try {
      await apiFetch('/auth/logout', { method: 'POST' })
    } finally {
      setAuthToken(null)
    }
  },
}

// ============== Users API ==============
export const usersApi = {
  list: async (params?: {
    login_type?: number
    subject?: string
    level?: string
    limit?: number
    offset?: number
  }): Promise<{ users: User[]; total: number }> => {
    const searchParams = new URLSearchParams()
    if (params?.login_type) searchParams.set('login_type', String(params.login_type))
    if (params?.subject) searchParams.set('subject', params.subject)
    if (params?.level) searchParams.set('level', params.level)
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    
    return apiFetch(`/users?${searchParams.toString()}`)
  },
  
  get: async (id: number): Promise<User> => {
    return apiFetch(`/users/${id}`)
  },
  
  update: async (id: number, data: Partial<User>): Promise<void> => {
    return apiFetch(`/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },
  
  delete: async (id: number): Promise<void> => {
    return apiFetch(`/users/${id}`, { method: 'DELETE' })
  },
  
  toggleAccess: async (id: number): Promise<void> => {
    return apiFetch(`/users/${id}/toggle-access`, { method: 'POST' })
  },
}

// ============== Students API ==============
export const studentsApi = {
  list: async (params?: {
    subject?: string
    level?: string
    group_id?: number
    limit?: number
    offset?: number
  }): Promise<{ students: User[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.subject) searchParams.set('subject', params.subject)
    if (params?.level) searchParams.set('level', params.level)
    if (params?.group_id) searchParams.set('group_id', String(params.group_id))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    
    return apiFetch(`/students?${searchParams.toString()}`)
  },
}

// ============== Groups API ==============
export const groupsApi = {
  list: async (): Promise<{ groups: Group[] }> => {
    return apiFetch('/groups')
  },
  
  create: async (data: { name: string; teacher_id?: number; level?: string }): Promise<{ id: number }> => {
    return apiFetch('/groups', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  
  delete: async (id: number): Promise<void> => {
    return apiFetch(`/groups/${id}`, { method: 'DELETE' })
  },
}

// ============== Articles API ==============
export const articlesApi = {
  list: async (params?: {
    subject?: string
    level?: string
    published_only?: boolean
  }): Promise<{ articles: Article[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.subject) searchParams.set('subject', params.subject)
    if (params?.level) searchParams.set('level', params.level)
    if (params?.published_only) searchParams.set('published_only', 'true')
    
    return apiFetch(`/articles?${searchParams.toString()}`)
  },
  
  get: async (id: number): Promise<Article> => {
    return apiFetch(`/articles/${id}`)
  },
  
  create: async (data: {
    title: string
    content: string
    subject: string
    level?: string
    visible_to_teachers?: boolean
    visible_to_support_teachers?: boolean
    visible_to_students?: boolean
    is_published?: boolean
  }): Promise<{ id: number }> => {
    return apiFetch('/articles', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  
  togglePublish: async (id: number): Promise<void> => {
    return apiFetch(`/articles/${id}/publish`, { method: 'PUT' })
  },
  
  delete: async (id: number): Promise<void> => {
    return apiFetch(`/articles/${id}`, { method: 'DELETE' })
  },
}

// ============== DCoin API ==============
export const dcoinApi = {
  getTransactions: async (params?: {
    student_id?: number
    limit?: number
  }): Promise<{ transactions: DCoinTransaction[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.student_id) searchParams.set('student_id', String(params.student_id))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    
    return apiFetch(`/dcoin/transactions?${searchParams.toString()}`)
  },
  
  createTransaction: async (data: {
    student_id: number
    amount: number
    transaction_type: string
    reason: string
  }): Promise<{ id: number }> => {
    return apiFetch('/dcoin/transactions', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  
  getBalance: async (student_id: number): Promise<{ balance: number }> => {
    return apiFetch(`/dcoin/balance/${student_id}`)
  },
  
  getLeaderboard: async (params?: {
    subject?: string
    limit?: number
  }): Promise<{ leaderboard: LeaderboardEntry[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.subject) searchParams.set('subject', params.subject)
    if (params?.limit) searchParams.set('limit', String(params.limit))
    
    return apiFetch(`/dcoin/leaderboard?${searchParams.toString()}`)
  },
}

// ============== Messages API ==============
export const messagesApi = {
  list: async (folder: 'inbox' | 'sent' = 'inbox'): Promise<{ messages: Message[] }> => {
    return apiFetch(`/messages?folder=${folder}`)
  },
  
  send: async (data: {
    recipient_id: number
    subject: string
    content: string
  }): Promise<{ id: number }> => {
    return apiFetch('/messages', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  
  markRead: async (id: number): Promise<void> => {
    return apiFetch(`/messages/${id}/read`, { method: 'PUT' })
  },
  
  delete: async (id: number): Promise<void> => {
    return apiFetch(`/messages/${id}`, { method: 'DELETE' })
  },
}

// ============== Vocabulary API ==============
export const vocabularyApi = {
  list: async (params?: {
    subject?: string
    level?: string
    language?: string
    search?: string
    limit?: number
    offset?: number
  }): Promise<{ words: VocabularyWord[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.subject) searchParams.set('subject', params.subject)
    if (params?.level) searchParams.set('level', params.level)
    if (params?.language) searchParams.set('language', params.language)
    if (params?.search) searchParams.set('search', params.search)
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    
    return apiFetch(`/vocabulary?${searchParams.toString()}`)
  },
  
  add: async (data: {
    word: string
    subject: string
    language?: string
    level?: string
    translation_uz?: string
    translation_ru?: string
    definition?: string
    example?: string
  }): Promise<{ id: number }> => {
    return apiFetch('/vocabulary', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
}

// ============== Daily Tests API ==============
export const dailyTestsApi = {
  checkAvailable: async (): Promise<{ available: boolean; test_date?: string; message?: string }> => {
    return apiFetch('/daily-tests/available')
  },
  
  submit: async (data: {
    score: number
    max_score: number
    subject: string
    level: string
  }): Promise<{ id: number; dcoin_reward: number }> => {
    return apiFetch('/daily-tests/submit', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  
  getHistory: async (limit?: number): Promise<{ history: any[] }> => {
    const params = limit ? `?limit=${limit}` : ''
    return apiFetch(`/daily-tests/history${params}`)
  },
}

// ============== Stats API ==============
export const statsApi = {
  getDashboard: async (): Promise<DashboardStats> => {
    return apiFetch('/stats/dashboard')
  },
}

// ============== Reference Data API ==============
export const referenceApi = {
  getSubjects: async (): Promise<{ subjects: { id: string; name: string }[] }> => {
    return apiFetch('/subjects')
  },
  
  getLevels: async (subject?: string): Promise<{ levels: { id: string; name: string; order: number }[] }> => {
    const params = subject ? `?subject=${subject}` : ''
    return apiFetch(`/levels${params}`)
  },
}

// ============== Health Check ==============
export const healthApi = {
  check: async (): Promise<{ status: string; service: string }> => {
    return apiFetch('/health')
  },
}
