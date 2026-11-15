import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { EmptyState, ErrorBanner, LoadingBlock, StatusBadge } from '../components/ui'
import type { ContentSummary } from '../types'

export default function Queue() {
  const [items, setItems] = useState<ContentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setItems(await api.queue())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the queue.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-brand-900">Review queue</h1>
        <p className="mt-1 text-sm text-gray-600">
          Versions submitted for approval. Each decision applies to one exact version.
        </p>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {items === null ? (
        <LoadingBlock label="Loading the queue…" />
      ) : items.length === 0 ? (
        <EmptyState title="The queue is empty">
          When a creator submits a version for approval it appears here.
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="card flex flex-wrap items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-semibold text-charcoal">{item.title}</h3>
                <p className="text-xs text-gray-500">
                  v{item.version_no} · {item.content_type} · updated{' '}
                  {new Date(item.updated_at).toLocaleString()}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {item.open_high > 0 && (
                  <span className="badge bg-red-100 text-red-800">{item.open_high} high open</span>
                )}
                <StatusBadge status={item.status} />
                <Link to={`/approval/${item.id}`} className="btn-primary text-xs">
                  Review & decide
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
