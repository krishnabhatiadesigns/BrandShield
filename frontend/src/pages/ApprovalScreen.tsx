import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../components/AuthContext'
import {
  ErrorBanner,
  EvidenceBadge,
  LoadingBlock,
  SeverityBadge,
  Spinner,
  StatusBadge,
} from '../components/ui'
import type { ContentDetail } from '../types'

export default function ApprovalScreen() {
  const { id } = useParams()
  const itemId = Number(id)
  const { me } = useAuth()

  const [item, setItem] = useState<ContentDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [reason, setReason] = useState('')
  const [signoff, setSignoff] = useState(false)
  const [comment, setComment] = useState('')

  const canApprove = me?.role === 'approver' || me?.role === 'admin'

  const load = useCallback(async () => {
    setError(null)
    try {
      setItem(await api.getContent(itemId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load this submission.')
    }
  }, [itemId])

  useEffect(() => {
    void load()
  }, [load])

  const decide = async (decision: 'approved' | 'changes_requested' | 'rejected') => {
    setBusy(true)
    setError(null)
    try {
      setItem(await api.approve(itemId, decision, reason.trim() || null, signoff))
      setReason('')
      setSignoff(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That decision failed.')
    } finally {
      setBusy(false)
    }
  }

  const addComment = async () => {
    if (!comment.trim()) return
    setBusy(true)
    try {
      setItem(await api.comment(itemId, comment.trim()))
      setComment('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the comment.')
    } finally {
      setBusy(false)
    }
  }

  if (error && !item) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <ErrorBanner message={error} onRetry={() => void load()} />
        <Link to="/dashboard" className="btn-secondary">
          Back to dashboard
        </Link>
      </div>
    )
  }
  if (!item) return <LoadingBlock label="Loading the approval view…" />

  const version = item.current_version
  const unresolvedHigh = item.findings.filter(
    (f) => f.severity === 'high' && (f.creator_decision === 'pending' || f.creator_decision === 'rejected'),
  )
  const awaiting = version?.status === 'Approver Review'
  const latestApproval = item.approvals[item.approvals.length - 1]

  return (
    <div className="space-y-5">
      <div>
        <Link to={`/review/${itemId}`} className="text-xs font-semibold text-brand-700 hover:underline">
          ← Back to review
        </Link>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-brand-900">
          Approval · {item.title}
        </h1>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-600">
          <StatusBadge status={item.status} />
          <span>version {version?.version_no}</span>
          <span>·</span>
          <span>submitted by {version?.created_by}</span>
        </div>
      </div>

      {error && <ErrorBanner message={error} />}

      {latestApproval && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            latestApproval.decision === 'approved'
              ? 'border-brand-200 bg-brand-50 text-brand-900'
              : 'border-amber-200 bg-amber-50 text-amber-900'
          }`}
        >
          <strong className="font-semibold">
            {latestApproval.decision === 'approved'
              ? 'Approved'
              : latestApproval.decision === 'rejected'
                ? 'Rejected'
                : 'Changes requested'}
          </strong>{' '}
          by {latestApproval.reviewer}
          {latestApproval.reason ? ` — “${latestApproval.reason}”` : ''}
          {latestApproval.high_severity_signoff && ' (high-severity sign-off given)'}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Version {version?.version_no} content
          </h2>
          <div className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-brand-100 bg-white p-4 text-[15px] leading-relaxed">
            {version?.body}
          </div>
        </section>

        <div className="space-y-4">
          <section className="card p-4">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Unresolved high-severity findings ({unresolvedHigh.length})
            </h2>
            {unresolvedHigh.length === 0 ? (
              <p className="text-sm text-brand-800">
                No unresolved high-severity findings on this version.
              </p>
            ) : (
              <ul className="space-y-2">
                {unresolvedHigh.map((f) => (
                  <li key={f.id} className="rounded-lg border border-red-200 bg-red-50 p-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={f.severity} />
                      <EvidenceBadge status={f.evidence_status} />
                    </div>
                    <p className="mt-1 text-sm font-semibold text-red-900">{f.rule}</p>
                    <p className="mt-0.5 break-words font-mono text-xs text-red-800">
                      {f.affected_text}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card p-4">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Comments
            </h2>
            {item.comments.length === 0 ? (
              <p className="text-sm text-gray-500">No comments yet.</p>
            ) : (
              <ul className="space-y-2">
                {item.comments.map((c) => (
                  <li key={c.id} className="rounded-lg bg-gray-50 p-2.5 text-sm">
                    <div className="text-xs font-semibold text-charcoal">{c.author}</div>
                    <p className="mt-0.5 text-gray-700">{c.body}</p>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex gap-2">
              <input
                className="input"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add a comment for the creator…"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void addComment()
                }}
              />
              <button className="btn-secondary shrink-0" disabled={busy || !comment.trim()} onClick={() => void addComment()}>
                Post
              </button>
            </div>
          </section>

          {canApprove && awaiting && (
            <section className="card space-y-3 p-4">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                Your decision
              </h2>
              <div>
                <label className="label" htmlFor="reason">
                  Reason {unresolvedHigh.length > 0 ? '(required to request changes or reject)' : '(optional)'}
                </label>
                <textarea
                  id="reason"
                  className="input min-h-[70px]"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain your decision for the audit trail…"
                />
              </div>

              {unresolvedHigh.length > 0 && (
                <label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-sm text-amber-900">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={signoff}
                    onChange={(e) => setSignoff(e.target.checked)}
                  />
                  <span>
                    I have reviewed the {unresolvedHigh.length} unresolved high-severity
                    finding(s) and explicitly sign off on approving this version anyway.
                  </span>
                </label>
              )}

              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-primary"
                  disabled={busy || (unresolvedHigh.length > 0 && !signoff)}
                  onClick={() => void decide('approved')}
                >
                  {busy ? <Spinner /> : null}
                  Approve this version
                </button>
                <button
                  className="btn-secondary"
                  disabled={busy || !reason.trim()}
                  title="Sends the version back to the creator to fix"
                  onClick={() => void decide('changes_requested')}
                >
                  Send back to Creator
                </button>
                <button
                  className="btn-danger"
                  disabled={busy || !reason.trim()}
                  title="Ends this version permanently"
                  onClick={() => void decide('rejected')}
                >
                  Reject permanently
                </button>
              </div>
              <p className="text-[11px] text-gray-500">
                <strong className="font-semibold">Send back</strong> lets the creator fix and
                resubmit. <strong className="font-semibold">Reject</strong> ends this version.
              </p>
            </section>
          )}

          {canApprove && !awaiting && (
            <section className="card p-4 text-sm text-gray-600">
              This version is in <strong className="font-semibold">{version?.status}</strong>, so
              it is not waiting on you. A manager must forward it to the approver first.
            </section>
          )}

          {!canApprove && (
            <section className="card p-4 text-sm text-gray-600">
              You are signed in as {me?.role}. Only the approver can make the final decision.
              {me?.role === 'manager' && (
                <>
                  {' '}
                  Use <strong className="font-semibold">Send to Approver</strong> on the review
                  screen to forward this version.
                </>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
