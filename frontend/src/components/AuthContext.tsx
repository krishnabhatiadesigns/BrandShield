import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getToken, setToken } from '../api'
import type { Me } from '../types'

interface AuthState {
  me: Me | null
  loading: boolean
  waking: boolean
  error: string | null
  enterDemo: (role: 'creator' | 'manager' | 'approver') => Promise<void>
  signOut: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [waking, setWaking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setMe(null)
      setLoading(false)
      return
    }
    try {
      setMe(await api.me())
      setError(null)
    } catch {
      setToken(null)
      setMe(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const enterDemo = useCallback(async (role: 'creator' | 'manager' | 'approver') => {
    setError(null)
    setWaking(true)
    // The backend may be cold-starting. Poll /health so the user sees a clear
    // "waking up the server" message instead of a spinner that never resolves.
    const started = Date.now()
    let healthy = false
    while (Date.now() - started < 60000) {
      try {
        await api.health()
        healthy = true
        break
      } catch {
        await new Promise((r) => setTimeout(r, 2000))
      }
    }
    if (!healthy) {
      setWaking(false)
      setError('The server is taking longer than usual to wake up. Please try again.')
      return
    }
    try {
      const session = await api.demoSession(role)
      setToken(session.token)
      setMe(await api.me())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the demo.')
    } finally {
      setWaking(false)
    }
  }, [])

  const signOut = useCallback(() => {
    setToken(null)
    setMe(null)
  }, [])

  const value = useMemo(
    () => ({ me, loading, waking, error, enterDemo, signOut, refresh }),
    [me, loading, waking, error, enterDemo, signOut, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
