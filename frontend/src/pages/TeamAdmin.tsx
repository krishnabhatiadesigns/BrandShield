import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorBanner, LoadingBlock, Spinner } from '../components/ui'
import type { Role, WorkspaceMember } from '../types'

const ASSIGNABLE_ROLES: Role[] = ['creator', 'manager', 'approver', 'admin']

export default function TeamAdmin() {
  const [members, setMembers] = useState<WorkspaceMember[] | null>(null)
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [brandName, setBrandName] = useState('')
  const [role, setRole] = useState<Role>('creator')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setMembers(await api.members())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load workspace members.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const invite = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy('invite')
    setError(null)
    setNotice(null)
    try {
      await api.inviteMember({ email: email.trim(), display_name: displayName.trim(), role })
      setEmail('')
      setDisplayName('')
      setRole('creator')
      setNotice('Invitation sent. The employee can set a password from the email link.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not invite this employee.')
    } finally {
      setBusy(null)
    }
  }

  const update = async (member: WorkspaceMember, values: { role?: string; is_active?: boolean }) => {
    setBusy(member.user_id)
    setError(null)
    setNotice(null)
    try {
      await api.updateMember(member.user_id, values)
      setNotice('Workspace member updated.')
      await load()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not update this member.'
      await load()
      setError(message)
    } finally {
      setBusy(null)
    }
  }

  const createBrand = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy('brand')
    setError(null)
    setNotice(null)
    try {
      await api.createBrand(brandName.trim())
      setBrandName('')
      setNotice('Brand workspace created. Use the workspace selector to switch to it.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create this brand workspace.')
    } finally {
      setBusy(null)
    }
  }

  if (!members && !error) return <LoadingBlock label="Loading workspace members…" />

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-brand-900">Team access</h1>
        <p className="mt-1 text-sm text-gray-600">
          Invite employees and manage their workspace role and access.
        </p>
      </header>
      {error && <ErrorBanner message={error} onRetry={() => void load()} />}
      {notice && (
        <p className="rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm text-brand-900">
          {notice}
        </p>
      )}

      <form className="card space-y-3 p-4" onSubmit={(event) => void createBrand(event)}>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Add a brand workspace
        </h2>
        <p className="text-xs text-gray-600">
          The new brand starts with its own guidelines, terms, facts and palette. Existing
          employees are not granted access automatically.
        </p>
        <div className="flex flex-wrap gap-2">
          <input
            className="input max-w-sm"
            required
            minLength={2}
            maxLength={120}
            aria-label="New brand name"
            placeholder="Brand name"
            value={brandName}
            onChange={(event) => setBrandName(event.target.value)}
          />
          <button type="submit" className="btn-secondary" disabled={busy !== null}>
            {busy === 'brand' ? <Spinner /> : null}
            Create brand
          </button>
        </div>
      </form>

      <form className="card space-y-3 p-4" onSubmit={(event) => void invite(event)}>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Invite an employee
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <label>
            <span className="label">Name</span>
            <input
              className="input"
              required
              maxLength={120}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
          <label>
            <span className="label">Work email</span>
            <input
              className="input"
              type="email"
              required
              maxLength={254}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            <span className="label">Role</span>
            <select
              className="input"
              value={role}
              onChange={(event) => setRole(event.target.value as Role)}
            >
              {ASSIGNABLE_ROLES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button className="btn-primary" type="submit" disabled={busy !== null}>
          {busy === 'invite' ? <Spinner /> : null}
          Send invitation
        </button>
      </form>

      <section className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-3">Employee</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Access</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {(members ?? []).map((member) => (
              <tr key={member.user_id} className="border-t border-gray-100">
                <td className="px-4 py-3">
                  <div className="font-semibold text-charcoal">{member.display_name}</div>
                  <div className="text-xs text-gray-500">{member.email ?? 'No email recorded'}</div>
                </td>
                <td className="px-4 py-3">
                  <select
                    className="input h-9 py-1 text-xs"
                    value={member.role}
                    disabled={busy !== null}
                    aria-label={`Role for ${member.display_name}`}
                    onChange={(event) => void update(member, { role: event.target.value })}
                  >
                    {ASSIGNABLE_ROLES.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`badge ${
                      member.is_active ? 'bg-brand-100 text-brand-800' : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {member.is_active ? 'Active' : 'Deactivated'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    className={member.is_active ? 'btn-ghost text-xs text-red-700' : 'btn-secondary text-xs'}
                    disabled={busy !== null}
                    onClick={() => {
                      if (
                        member.is_active &&
                        !window.confirm(`Deactivate ${member.display_name}? Their access will be blocked.`)
                      ) {
                        return
                      }
                      void update(member, { is_active: !member.is_active })
                    }}
                  >
                    {busy === member.user_id ? <Spinner className="h-3 w-3" /> : null}
                    {member.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
            {members?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                  No employees have been added to this workspace yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  )
}
