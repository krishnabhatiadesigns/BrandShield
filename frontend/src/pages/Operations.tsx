import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorBanner, LoadingBlock, Spinner } from '../components/ui'

export default function OperationsPage() {
  const [analytics, setAnalytics] = useState<Awaited<ReturnType<typeof api.operationsAnalytics>> | null>(null)
  const [apiKeys, setApiKeys] = useState<Awaited<ReturnType<typeof api.apiKeys>> | null>(null)
  const [webhooks, setWebhooks] = useState<Awaited<ReturnType<typeof api.webhooks>> | null>(null)
  const [keyName, setKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [webhookName, setWebhookName] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [metrics, keys, endpoints] = await Promise.all([
        api.operationsAnalytics(),
        api.apiKeys(),
        api.webhooks(),
      ])
      setAnalytics(metrics)
      setApiKeys(keys)
      setWebhooks(endpoints)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load operations.')
    }
  }, [])

  useEffect(() => { void load() }, [load])

  if (!analytics && !error) return <LoadingBlock label="Loading operations…" />

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-brand-900">Operations</h1>
        <p className="mt-1 text-sm text-gray-600">Workspace analytics, audit exports, API keys and webhook delivery.</p>
      </header>
      {error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {analytics && (
        <section className="grid gap-3 sm:grid-cols-3">
          {[
            ['Submissions', analytics.submissions],
            ['Approved versions', analytics.approved_versions],
            ['Findings', analytics.findings],
          ].map(([label, value]) => (
            <div key={String(label)} className="card p-4">
              <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
              <div className="mt-1 text-2xl font-bold text-brand-900">{value}</div>
            </div>
          ))}
        </section>
      )}

      <button className="btn-secondary" onClick={() => { void api.downloadAuditCsv().catch((err) => setError(err instanceof Error ? err.message : 'Could not export audit.')) }}>
        Download audit CSV
      </button>

      <section className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">API keys</h2>
        <div className="flex flex-wrap gap-2">
          <input className="input max-w-sm" value={keyName} maxLength={120}
            onChange={(event) => setKeyName(event.target.value)} placeholder="Integration name" />
          <button className="btn-primary" disabled={busy || !keyName.trim()} onClick={async () => {
            setBusy(true); setError(null); setCreatedKey(null)
            try {
              const created = await api.createApiKey(keyName.trim(), ['read'])
              setCreatedKey(created.key)
              setKeyName('')
              await load()
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Could not create API key.')
            } finally { setBusy(false) }
          }}>
            {busy ? <Spinner /> : null}Create read key
          </button>
        </div>
        {createdKey && (
          <p className="break-all rounded bg-amber-50 p-3 text-xs">
            <strong>Copy now:</strong> <code>{createdKey}</code>
          </p>
        )}
        <div className="space-y-2">
          {(apiKeys ?? []).map((key) => (
            <div key={key.id} className="flex justify-between border-t pt-2 text-sm">
              <span>{key.name} · {key.key_prefix}… · {key.scopes}</span>
              <span className="text-xs text-gray-500">{key.is_active ? 'Active' : 'Disabled'}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Webhooks</h2>
        <div className="grid gap-2 sm:grid-cols-3">
          <input className="input" value={webhookName} maxLength={120}
            onChange={(event) => setWebhookName(event.target.value)} placeholder="Name" />
          <input className="input" value={webhookUrl} maxLength={2000}
            onChange={(event) => setWebhookUrl(event.target.value)} placeholder="https://example.com/webhook" />
          <input className="input" value={webhookSecret} maxLength={200}
            onChange={(event) => setWebhookSecret(event.target.value)} placeholder="Signing secret (16+ chars)" />
        </div>
        <button className="btn-primary" disabled={busy || !webhookName.trim() || !webhookUrl.trim() || webhookSecret.length < 16}
          onClick={async () => {
            setBusy(true); setError(null)
            try {
              await api.createWebhook({
                name: webhookName.trim(),
                url: webhookUrl.trim(),
                secret: webhookSecret,
                events: ['*'],
              })
              setWebhookName(''); setWebhookUrl(''); setWebhookSecret('')
              await load()
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Could not create webhook.')
            } finally { setBusy(false) }
          }}>
          {busy ? <Spinner /> : null}Create signed webhook
        </button>
        <div className="space-y-2">
          {(webhooks ?? []).map((hook) => (
            <div key={hook.id} className="border-t pt-2 text-sm">
              <div className="font-semibold">{hook.name}</div>
              <div className="break-all text-xs text-gray-500">{hook.url} · {hook.events}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
