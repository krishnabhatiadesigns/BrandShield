import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../components/AuthContext'
import { EmptyState, ErrorBanner, LoadingBlock, StatusBadge } from '../components/ui'
import type { ContentSummary } from '../types'

const TYPE_LABEL: Record<string, string> = {
  social: 'Social post',
  ad: 'Ad',
  email: 'Email',
  document: 'Document',
}

function SummaryCard({
  item,
  canViewHistory,
}: {
  item: ContentSummary
  canViewHistory: boolean
}) {
  return (
    <div className="card p-4 transition-shadow hover:shadow-md">
      <Link to={`/review/${item.id}`} className="block">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-charcoal">{item.title}</h3>
            <p className="mt-0.5 text-xs text-gray-500">
              {TYPE_LABEL[item.content_type] ?? item.content_type} · v{item.version_no}
            </p>
          </div>
          <StatusBadge status={item.status} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {item.open_high > 0 && (
            <span className="badge bg-red-100 text-red-800">{item.open_high} high open</span>
          )}
          {item.needs_verification > 0 && (
            <span className="badge bg-purple-100 text-purple-800">
              {item.needs_verification} need verification
            </span>
          )}
          {item.open_high === 0 && item.needs_verification === 0 && (
            <span className="badge bg-brand-100 text-brand-800">No open high-severity items</span>
          )}
        </div>
      </Link>
      {canViewHistory && (
        <Link
          to={`/history/${item.id}`}
          className="mt-2 inline-block text-xs font-semibold text-brand-700 hover:underline"
        >
          View past changes
        </Link>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { me } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState<ContentSummary[] | null>(null)
  const [queue, setQueue] = useState<ContentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canReview = me?.role === 'manager' || me?.role === 'approver' || me?.role === 'admin'
  const canCreate = me?.role === 'creator' || me?.role === 'admin'
  const canViewHistory = me?.role === 'approver'

  const load = useCallback(async () => {
    setError(null)
    try {
      const [list, q] = await Promise.all([
        api.listContent(),
        canReview ? api.queue() : Promise.resolve([]),
      ])
      setItems(list)
      setQueue(q)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your submissions.')
    }
  }, [canReview])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-brand-900">
            Hello, {me?.display_name.split(' ')[0]}
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {me?.workspace_name} · signed in as {me?.role}
          </p>
        </div>
        {canCreate ? (
          <button className="btn-primary" onClick={() => navigate('/new')}>
            New submission
          </button>
        ) : (
          <span className="rounded-lg border border-brand-200 bg-white px-3 py-2 text-xs text-gray-600">
            Reviewers cannot author content
          </span>
        )}
      </div>
      <section className="card p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          The loop
        </h2>
        <ol className="mt-3 grid gap-3 sm:grid-cols-3">
          {[
            ['1', 'Submit', 'Paste a draft or load a sample.'],
            ['2', 'Review findings', 'Each issue cites an approved source.'],
            ['3', 'Approve', 'A human approves that exact version.'],
          ].map(([n, title, text]) => (
            <li key={n} className="flex items-start gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-bold text-white">
                {n}
              </span>
              <div>
                <div className="text-sm font-semibold text-charcoal">{title}</div>
                <div className="text-xs text-gray-600">{text}</div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {canViewHistory && (
        <section
          className="rounded-2xl border-2 border-gold-400 bg-gradient-to-r from-amber-50 via-white to-gold-50 p-4 shadow-md sm:p-5"
          aria-labelledby="approver-history-note"
        >
          <div className="flex items-start gap-3">
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gold-400 text-lg font-black text-charcoal shadow-sm"
              aria-hidden="true"
            >
              !
            </span>
            <div>
              <h2
                id="approver-history-note"
                className="text-sm font-extrabold uppercase tracking-wide text-brand-900"
              >
                Before you approve, verify what changed
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-gray-700">
                Open a submission and select{' '}
                <strong className="font-bold text-brand-900">View past changes</strong> to compare
                versions. Check whether employees edited the draft or passed the AI response along
                unchanged.
              </p>
            </div>
          </div>
        </section>
      )}

      {error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {canReview && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-charcoal">Review queue</h2>
            <Link to="/queue" className="text-sm font-semibold text-brand-700 hover:underline">
              Open queue →
            </Link>
          </div>
          {queue === null ? (
            <LoadingBlock label="Loading the review queue…" />
          ) : queue.length === 0 ? (
            <EmptyState title="Nothing waiting for review">
              Submitted versions appear here for managers and approvers.
            </EmptyState>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {queue.slice(0, 6).map((item) => (
                <SummaryCard key={item.id} item={item} canViewHistory={canViewHistory} />
              ))}
            </div>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-charcoal">
          {canCreate ? 'My submissions' : 'All submissions'}
        </h2>
        {items === null ? (
          <LoadingBlock label="Loading submissions…" />
        ) : items.length === 0 ? (
          <EmptyState
            title="No submissions yet"
            action={
              <button className="btn-primary" onClick={() => navigate('/new')}>
                Create your first submission
              </button>
            }
          >
            Start with a sample draft to see the full check → findings → approval loop.
          </EmptyState>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <SummaryCard key={item.id} item={item} canViewHistory={canViewHistory} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
