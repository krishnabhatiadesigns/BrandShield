import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../components/AuthContext'
import { ErrorBanner, LoadingBlock, Spinner } from '../components/ui'
import type { ContentType, SampleInfo } from '../types'

const TYPES: { value: ContentType; label: string }[] = [
  { value: 'social', label: 'Social post' },
  { value: 'ad', label: 'Ad' },
  { value: 'email', label: 'Email' },
  { value: 'document', label: 'Document' },
]

export default function NewSubmission() {
  const navigate = useNavigate()
  const { me } = useAuth()
  const [samples, setSamples] = useState<SampleInfo[] | null>(null)
  const [title, setTitle] = useState('')
  const [contentType, setContentType] = useState<ContentType>('social')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadedSample, setLoadedSample] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api
      .samples()
      .then(setSamples)
      .catch(() => setSamples([]))
  }, [])

  const loadSample = (sample: SampleInfo) => {
    setTitle(sample.title)
    setContentType(sample.content_type)
    setBody(sample.body)
    setLoadedSample(sample.key)
    setError(null)
  }

  const submit = async () => {
    if (!title.trim() || !body.trim()) {
      setError('Add a title and some content before running the check.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const created = await api.createContent({
        title: title.trim(),
        content_type: contentType,
        body,
      })
      const reviewed = await api.review(created.id)
      navigate(`/review/${reviewed.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not run the check.')
    } finally {
      setBusy(false)
    }
  }

  const upload = async (file: File) => {
    setBusy(true)
    setError(null)
    try {
      const created = await api.uploadContent(file, title.trim() || file.name, contentType)
      const reviewed = await api.review(created.id)
      navigate(`/review/${reviewed.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not read that file.')
    } finally {
      setBusy(false)
    }
  }

  const canCreate = me?.role === 'creator' || me?.role === 'admin'

  if (!canCreate) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="card p-6 text-center">
          <h1 className="text-lg font-bold text-charcoal">Only creators can author content</h1>
          <p className="mt-2 text-sm text-gray-600">
            You are signed in as <strong className="font-semibold">{me?.role}</strong>. To keep
            review independent, the person who writes a draft cannot be the person who reviews or
            approves it.
          </p>
          <Link to="/dashboard" className="btn-primary mt-4">
            Back to dashboard
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-brand-900">New submission</h1>
        <p className="mt-1 text-sm text-gray-600">
          Paste your draft or upload a file. The check runs against this workspace's approved
          guidelines only.
        </p>
      </div>
      {error && <ErrorBanner message={error} />}

      <section className="card p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Load a sample draft
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Each sample contains real planted errors so you can see the pipeline work immediately.
        </p>
        {samples === null ? (
          <LoadingBlock label="Loading samples…" />
        ) : (
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {samples.map((sample) => (
              <button
                key={sample.key}
                type="button"
                onClick={() => loadSample(sample)}
                className={`rounded-lg border p-3 text-left text-sm transition-colors ${
                  loadedSample === sample.key
                    ? 'border-brand-600 bg-brand-50'
                    : 'border-brand-200 bg-white hover:bg-brand-50'
                }`}
              >
                <div className="font-semibold text-charcoal">{sample.title}</div>
                <div className="mt-0.5 text-xs text-gray-500">
                  {TYPES.find((t) => t.value === sample.content_type)?.label}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="card space-y-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="title">
              Title
            </label>
            <input
              id="title"
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. LinkedIn launch post"
              maxLength={200}
            />
          </div>
          <div>
            <label className="label" htmlFor="type">
              Content type
            </label>
            <select
              id="type"
              className="input"
              value={contentType}
              onChange={(e) => setContentType(e.target.value as ContentType)}
            >
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              Content type decides which disclaimer is required.
            </p>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="body">
            Draft content
          </label>
          <textarea
            id="body"
            className="input min-h-[220px] font-mono text-[13px] leading-relaxed"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Paste the content you want to check before publication…"
            maxLength={20000}
          />
          <div className="mt-1 flex justify-between text-xs text-gray-500">
            <span>{body.length.toLocaleString()} / 20,000 characters</span>
            {loadedSample && <span>Sample loaded — edit freely</span>}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button className="btn-primary" onClick={() => void submit()} disabled={busy}>
            {busy ? <Spinner /> : null}
            {busy ? 'Running the check…' : 'Run review'}
          </button>

          <span className="text-xs text-gray-400">or</span>

          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void upload(file)
              e.target.value = ''
            }}
          />
          <button
            type="button"
            className="btn-secondary"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            Upload a file
          </button>
        </div>
        <p className="text-xs text-gray-500">
          Upload PDF, DOCX, TXT or Markdown. Scanned PDFs without selectable text are rejected
          with a clear message rather than silently returning nothing.
        </p>
      </section>
    </div>
  )
}
