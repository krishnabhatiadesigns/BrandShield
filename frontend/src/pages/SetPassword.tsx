import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../components/AuthContext'
import { ErrorBanner, Spinner } from '../components/ui'
import { supabase } from '../supabase'

export default function SetPassword() {
  const { updatePassword } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const save = async () => {
    if (!supabase) {
      setError('Business sign-in is not configured for this deployment.')
      return
    }
    if (password.length < 12) {
      setError('Use at least 12 characters for your password.')
      return
    }
    if (password !== confirmation) {
      setError('The passwords do not match.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const { data } = await supabase.auth.getSession()
      if (!data.session) {
        setError('Open the latest password setup or recovery link sent to your email.')
        return
      }
      await updatePassword(password)
      setNotice('Password updated.')
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update your password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-cream px-4 py-12">
      <section className="card mx-auto max-w-lg space-y-4 p-6">
        <Link to="/" className="text-xs font-semibold text-brand-700 hover:underline">
          ← BrandShield
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-brand-900">Set your password</h1>
          <p className="mt-1 text-sm text-gray-600">
            Choose a strong password to finish joining your BrandShield workspace or recover your
            account.
          </p>
        </div>
        {error && <ErrorBanner message={error} />}
        {notice && <p className="rounded-lg bg-brand-50 p-3 text-sm text-brand-900">{notice}</p>}
        <label className="block">
          <span className="label">New password</span>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            minLength={12}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <label className="block">
          <span className="label">Confirm password</span>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            minLength={12}
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="btn-primary w-full"
          disabled={busy || !password || !confirmation}
          onClick={() => void save()}
        >
          {busy ? <Spinner /> : null}
          Save password
        </button>
      </section>
    </div>
  )
}
