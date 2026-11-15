import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { Diff, ErrorBanner, LoadingBlock, StatusBadge } from '../components/ui'
import type { AuditEvent, HistoryVersion } from '../types'

export default function HistoryPage() {
  const { id } = useParams()
  const itemId = id ? Number(id) : null

  const [versions, setVersions] = useState<HistoryVersion[] | null>(null)
  const [audit, setAudit] = useState<AuditEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [v, a] = await Promise.all([
        itemId ? api.history(itemId) : Promise.resolve([]),
        itemId ? api.contentAudit(itemId) : api.audit(),
      ])
      setVersions(v)
      setAudit(a)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the history.')
    }
  }, [itemId])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-brand-900">
          {itemId ? 'Version history' : 'Audit trail'}
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          {itemId
            ? 'Every version, decision and approval for this submission only. An approval applies to one exact version.'
            : 'Workspace-wide audit trail. Open a submission to see its own version history.'}
        </p>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {itemId && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-charcoal">Versions</h2>
          {versions === null ? (
            <LoadingBlock label="Loading versions…" />
          ) : (
            <div className="space-y-3">
              {versions.map((v, index) => (
                <article key={v.version_id} className="card p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-charcoal">v{v.version_no}</span>
                    <StatusBadge status={v.status} />
                    <span className="text-xs text-gray-500">
                      {v.finding_count} findings · {v.created_by} ·{' '}
                      {new Date(v.created_at).toLocaleString()}
                    </span>
                    <Link
                      to={`/review/${itemId}`}
                      className="ml-auto text-xs font-semibold text-brand-700 hover:underline"
                    >
                      Open
                    </Link>
                  </div>
                  {index === 0 ? (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs font-semibold text-brand-700">
                        View original submission
                      </summary>
                      <p className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                        {v.body}
                      </p>
                    </details>
                  ) : (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs font-semibold text-brand-700">
                        View changes in this version
                      </summary>
                      <div className="mt-2">
                        <Diff before={versions[index - 1].body} after={v.body} />
                      </div>
                    </details>
                  )}
                  {v.approvals.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {v.approvals.map((a, i) => (
                        <li key={i} className="text-xs text-gray-600">
                          <strong className="font-semibold">{a.decision}</strong> by {a.reviewer}
                          {a.reason ? ` — “${a.reason}”` : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-charcoal">
          {itemId ? 'Activity for this submission' : 'Audit trail'}
        </h2>
        {audit === null ? (
          <LoadingBlock label="Loading the audit trail…" />
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-2">When</th>
                  <th className="px-4 py-2">Actor</th>
                  <th className="px-4 py-2">Action</th>
                  <th className="px-4 py-2">Detail</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((e) => (
                  <tr key={e.id} className="border-t border-gray-100">
                    <td className="whitespace-nowrap px-4 py-2 text-xs text-gray-500">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2">{e.actor}</td>
                    <td className="px-4 py-2 font-mono text-xs">{e.action}</td>
                    <td className="px-4 py-2 text-gray-600">{e.detail ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
