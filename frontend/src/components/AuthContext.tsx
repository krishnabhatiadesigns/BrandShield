import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  api,
  ApiError,
  getToken,
  getTokenType,
  setToken,
  setWorkspaceId,
} from '../api'
import { demoAuthEnabled, supabase, supabaseAuthEnabled } from '../supabase'
import type { Me, Workspace } from '../types'

interface AuthState {
  me: Me | null
  workspaces: Workspace[]
  loading: boolean
  waking: boolean
  error: string | null
  authEnabled: boolean
  demoEnabled: boolean
  organizationCreationEnabled: boolean
  needsOrganizationSetup: boolean
  enterDemo: (role: 'creator' | 'manager' | 'approver') => Promise<boolean>
  signIn: (email: string, password: string) => Promise<void>
  sendPasswordReset: (email: string) => Promise<void>
  updatePassword: (password: string) => Promise<void>
  createOrganization: (payload: {
    name: string
    brand_name?: string
    display_name: string
  }) => Promise<void>
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
  const [needsOrganizationSetup, setNeedsOrganizationSetup] = useState(false)

  const loadPrincipal = useCallback(async (token: string, type: 'demo' | 'supabase') => {
    setToken(token, type)
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
      setNeedsOrganizationSetup(false)
      setError(null)
    } catch (err) {
      setMe(null)
      setWorkspaces([])
      const message = err instanceof Error ? err.message : 'Could not verify your account.'
      setNeedsOrganizationSetup(
        type === 'supabase' &&
          err instanceof ApiError &&
          err.status === 403 &&
          message.toLowerCase().includes('not an active member'),
      )
      setError(message)
      throw new Error(message)
    } finally {
      setLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    if (supabase) {
      const { data, error: sessionError } = await supabase.auth.getSession()
      if (sessionError) {
        setError(sessionError.message)
        setLoading(false)
        return
      }
      const accessToken = data.session?.access_token
      if (accessToken) {
        try {
          await loadPrincipal(accessToken, 'supabase')
        } catch {
          // loadPrincipal surfaces the provider/API error in context state.
        }
        return
      }
    }

    const token = getToken()
    if (token && getTokenType() === 'demo') {
      try {
        await loadPrincipal(token, 'demo')
      } catch {
        // loadPrincipal surfaces the provider/API error in context state.
      }
    } else {
      setToken(null)
      setMe(null)
      setWorkspaces([])
      setNeedsOrganizationSetup(false)
      setLoading(false)
    }
  }, [loadPrincipal])

  useEffect(() => {
    if (!supabase) {
      void refresh()
      return
    }
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.access_token) {
        void loadPrincipal(session.access_token, 'supabase').catch(() => undefined)
      } else {
        setToken(null)
        setMe(null)
        setWorkspaces([])
        setNeedsOrganizationSetup(false)
        setLoading(false)
      }
    })
    void refresh()
    return () => subscription.unsubscribe()
  }, [loadPrincipal, refresh])

  const signIn = useCallback(
    async (email: string, password: string) => {
      setError(null)
      if (!supabase) throw new Error('Business sign-in is not configured for this deployment.')
      const { data, error: signInError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      })
      if (signInError) throw signInError
      if (!data.session?.access_token) {
        throw new Error('Sign-in did not return a session. Check your email verification.')
      }
      await loadPrincipal(data.session.access_token, 'supabase')
    },
    [loadPrincipal],
  )

  const sendPasswordReset = useCallback(async (email: string) => {
    setError(null)
    if (!supabase) throw new Error('Business sign-in is not configured for this deployment.')
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/set-password`,
    })
    if (resetError) throw resetError
  }, [])

  const updatePassword = useCallback(
    async (password: string) => {
      if (!supabase) throw new Error('Business sign-in is not configured for this deployment.')
      const { data, error: updateError } = await supabase.auth.updateUser({ password })
      if (updateError) throw updateError
      if (!data.user) throw new Error('The authentication provider did not return your account.')
      await refresh()
    },
    [refresh],
  )

  const createOrganization = useCallback(
    async (payload: { name: string; brand_name?: string; display_name: string }) => {
      const created = await api.createOrganization(payload)
      setWorkspaceId(created.workspace_id)
      await refresh()
    },
    [refresh],
  )

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
      await loadPrincipal(session.token, 'demo')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the demo.')
      return false
    } finally {
      setWaking(false)
    }
  }, [loadPrincipal])

  const signOut = useCallback(() => {
    const type = getTokenType()
    setError(null)
    if (type === 'supabase' && supabase) {
      void supabase.auth.signOut().then(({ error: signOutError }) => {
        setToken(null)
        setWorkspaceId(null)
        setMe(null)
        setWorkspaces([])
        if (signOutError) {
          setError(`Signed out locally, but provider sign-out failed: ${signOutError.message}`)
        }
      }).catch((err: unknown) => {
        setToken(null)
        setWorkspaceId(null)
        setMe(null)
        setWorkspaces([])
        setError(
          err instanceof Error
            ? `Signed out locally, but provider sign-out failed: ${err.message}`
            : 'Signed out locally, but provider sign-out failed.',
        )
      })
    } else {
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
    }
    setNeedsOrganizationSetup(false)
    setLoading(false)
  }, [])

  const value = useMemo(
    () => ({
      me,
      workspaces,
      loading,
      waking,
      error,
      authEnabled: supabaseAuthEnabled,
      demoEnabled: demoAuthEnabled,
      organizationCreationEnabled:
        import.meta.env.VITE_ORGANIZATION_CREATION_ENABLED === 'true',
      needsOrganizationSetup,
      enterDemo,
      signIn,
      sendPasswordReset,
      updatePassword,
      createOrganization,
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
      needsOrganizationSetup,
      enterDemo,
      signIn,
      sendPasswordReset,
      updatePassword,
      createOrganization,
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
