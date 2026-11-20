import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError, getToken, setToken, setWorkspaceId } from '../api'
import type { Me, Workspace } from '../types'

interface AuthState {
  me: Me | null
  workspaces: Workspace[]
  loading: boolean
  waking: boolean
  error: string | null
  enterDemo: (role: 'creator' | 'manager' | 'approver') => Promise<boolean>
  switchWorkspace: (workspaceId: number) => Promise<void>
  signOut: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [waking, setWaking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadPrincipal = useCallback(async (token: string) => {
    setToken(token)
    try {
      let principal: Me
      try {
        principal = await api.me()
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 403) throw err
        setWorkspaceId(null)
        principal = await api.me()
      }
      const availableWorkspaces = await api.workspaces()
      setMe(principal)
      setWorkspaces(availableWorkspaces)
      setWorkspaceId(principal.workspace_id)
      setError(null)
    } catch (err) {
      setMe(null)
      setWorkspaces([])
      const message = err instanceof Error ? err.message : 'Could not verify your account.'
      setError(message)
      throw new Error(message)
    } finally {
      setLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    const token = getToken()
    if (token) {
      try {
        await loadPrincipal(token)
      } catch {
        // loadPrincipal surfaces the provider/API error in context state.
      }
    } else {
      setToken(null)
      setMe(null)
      setWorkspaces([])
      setError(null)
      setLoading(false)
    }
  }, [loadPrincipal])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const switchWorkspace = useCallback(
    async (workspaceId: number) => {
      if (!workspaces.some((workspace) => workspace.id === workspaceId)) {
        throw new Error('You do not have access to that workspace.')
      }
      const previousWorkspaceId = me?.workspace_id ?? null
      setWorkspaceId(workspaceId)
      try {
        const principal = await api.me()
        setMe(principal)
        setError(null)
      } catch (err) {
        setWorkspaceId(previousWorkspaceId)
        throw err
      }
    },
    [workspaces, me],
  )

  const enterDemo = useCallback(async (role: 'creator' | 'manager' | 'approver') => {
    setError(null)
    setWaking(true)
    const started = Date.now()
    let healthy = false
    while (Date.now() - started < 60000) {
      try {
        await api.health()
        healthy = true
        break
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 2000))
      }
    }
    if (!healthy) {
      setWaking(false)
      setError('The server is taking longer than usual to wake up. Please try again.')
      return false
    }
    try {
      const session = await api.demoSession(role)
      await loadPrincipal(session.token)
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the demo.')
      return false
    } finally {
      setWaking(false)
    }
  }, [loadPrincipal])

  const signOut = useCallback(() => {
    setError(null)
    void api.logout().catch((err: unknown) => {
      setError(
        err instanceof Error
          ? `Signed out locally, but server revocation failed: ${err.message}`
          : 'Signed out locally, but server revocation failed.',
      )
    })
    setToken(null)
    setWorkspaceId(null)
    setMe(null)
    setWorkspaces([])
    setLoading(false)
  }, [])

  const value = useMemo(
    () => ({
      me,
      workspaces,
      loading,
      waking,
      error,
      enterDemo,
      switchWorkspace,
      signOut,
      refresh,
    }),
    [
      me,
      workspaces,
      loading,
      waking,
      error,
      enterDemo,
      switchWorkspace,
      signOut,
      refresh,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
