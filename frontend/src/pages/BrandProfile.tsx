import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../components/AuthContext'
import { ErrorBanner, LoadingBlock, Spinner } from '../components/ui'
import type { BrandProfile, VisualCheckResponse } from '../types'

type Tab = 'context' | 'guidelines' | 'terms' | 'facts' | 'palette' | 'visual'

export default function BrandProfilePage() {
  const { me } = useAuth()
  const [profile, setProfile] = useState<BrandProfile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('context')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const canEdit = me?.role === 'manager' || me?.role === 'admin'

  const load = useCallback(async () => {
    setError(null)
    try {
      setProfile(await api.brand())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the brand profile.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await fn()
      await load()
      setNotice(message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That change failed.')
    } finally {
      setBusy(false)
    }
  }

  if (error && !profile) {
    return <ErrorBanner message={error} onRetry={() => void load()} />
  }
  if (!profile) return <LoadingBlock label="Loading the brand profile…" />

  const tabs: { key: Tab; label: string }[] = [
    { key: 'context', label: 'Company context' },
    { key: 'guidelines', label: `Guidelines (${profile.passages.length})` },
    { key: 'terms', label: `Terminology (${profile.terms.length})` },
    { key: 'facts', label: `Facts (${profile.facts.length})` },
    { key: 'palette', label: 'Palette' },
    { key: 'visual', label: 'Visual check' },
  ]

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-brand-900">Brand profile</h1>
        <p className="mt-1 text-sm text-gray-600">
          {profile.workspace_name} · the approved knowledge every check runs against.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}
      {notice && (
        <div className="rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm text-brand-900">
          {notice}
        </div>
      )}

      <div className="flex flex-wrap gap-1 border-b border-brand-100 pb-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              tab === t.key ? 'bg-brand-700 text-white' : 'text-brand-800 hover:bg-brand-50'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'context' && (
        <CompanyContextTab profile={profile} canEdit={canEdit} busy={busy} run={run} />
      )}
      {tab === 'guidelines' && (
        <GuidelinesTab profile={profile} canEdit={canEdit} busy={busy} run={run} />
      )}
      {tab === 'terms' && <TermsTab profile={profile} canEdit={canEdit} busy={busy} run={run} />}
      {tab === 'facts' && <FactsTab profile={profile} canEdit={canEdit} busy={busy} run={run} />}
      {tab === 'palette' && (
        <PaletteTab profile={profile} canEdit={canEdit} busy={busy} run={run} />
      )}
      {tab === 'visual' && <VisualTab />}
    </div>
  )
}

type RunFn = (fn: () => Promise<unknown>, message: string) => Promise<void>

function CompanyContextTab({
  profile,
  canEdit,
  busy,
  run,
}: {
  profile: BrandProfile
  canEdit: boolean
  busy: boolean
  run: RunFn
}) {
  const [companyContext, setCompanyContext] = useState(profile.company_context)

  return (
    <section className="card space-y-3 p-4">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Company guidelines and context
        </h2>
        <p className="mt-1 text-xs text-gray-600">
          This workspace-specific background is sent to AI on every review. Use it for company
          facts, audience, tone, and priorities; approved passages remain the source for factual
          evidence.
        </p>
      </div>
      <textarea
        className="input min-h-[160px]"
        maxLength={10000}
        aria-label="Company guidelines and context"
        placeholder="Describe your company, products, audience, tone, or other context the AI should consider…"
        value={companyContext}
        disabled={!canEdit}
        onChange={(e) => setCompanyContext(e.target.value)}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-gray-500">{companyContext.length}/10,000 characters</span>
        {canEdit ? (
          <button
            className="btn-primary"
            disabled={busy || companyContext === profile.company_context}
            onClick={() =>
              void run(
                () => api.updateCompanyContext(companyContext),
                'Company context saved and will be included in future AI reviews.',
              )
            }
          >
            {busy ? <Spinner /> : null}
            Save company context
          </button>
        ) : (
          <span className="text-xs text-gray-500">
            Only managers and admins can edit company context.
          </span>
        )}
      </div>
    </section>
  )
}

function GuidelinesTab({
  profile,
  canEdit,
  busy,
  run,
}: {
  profile: BrandProfile
  canEdit: boolean
  busy: boolean
  run: RunFn
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [source, setSource] = useState('')
  const [section, setSection] = useState('')
  const [text, setText] = useState('')

  return (
    <div className="space-y-4">
      {canEdit && (
        <section className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Add a guideline passage
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="input"
              placeholder="Source document title"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            />
            <input
              className="input"
              placeholder="Section (optional)"
              value={section}
              onChange={(e) => setSection(e.target.value)}
            />
          </div>
          <textarea
            className="input min-h-[80px]"
            placeholder="The approved guideline text…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <button
              className="btn-primary"
              disabled={busy || !source.trim() || !text.trim()}
              onClick={() =>
                void run(
                  () =>
                    api.addPassage({
                      source: source.trim(),
                      section: section.trim() || undefined,
                      text: text.trim(),
                    }),
                  'Guideline passage added and is now in force.',
                ).then(() => {
                  setSource('')
                  setSection('')
                  setText('')
                })
              }
            >
              {busy ? <Spinner /> : null}
              Add passage
            </button>

            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) {
                  void run(
                    () => api.uploadGuideline(file, file.name),
                    'Guideline PDF ingested into approved passages.',
                  )
                }
                e.target.value = ''
              }}
            />
            <button
              className="btn-secondary"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              Upload guideline PDF
            </button>
          </div>
        </section>
      )}

      <div className="space-y-2">
        {profile.passages.map((p) => (
          <article key={p.id} className="card p-4">
            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
              <span className="badge bg-brand-100 text-brand-800">approved</span>
              <span className="font-semibold text-charcoal">{p.source}</span>
              {p.section && <span>· {p.section}</span>}
              {p.page && <span>· p.{p.page}</span>}
              <span className="ml-auto font-mono text-[11px]">#{p.id}</span>
            </div>
            <p className="mt-1.5 text-sm text-gray-700">{p.text}</p>
          </article>
        ))}
      </div>
    </div>
  )
}

function TermsTab({
  profile,
  canEdit,
  busy,
  run,
}: {
  profile: BrandProfile
  canEdit: boolean
  busy: boolean
  run: RunFn
}) {
  const [term, setTerm] = useState('')
  const [kind, setKind] = useState<'approved' | 'prohibited'>('prohibited')
  const [replacement, setReplacement] = useState('')

  const approved = profile.terms.filter((t) => t.kind === 'approved')
  const prohibited = profile.terms.filter((t) => t.kind === 'prohibited')

  return (
    <div className="space-y-4">
      {canEdit && (
        <section className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Add a term
          </h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <input
              className="input"
              placeholder="Term"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
            />
            <select
              className="input"
              value={kind}
              onChange={(e) => setKind(e.target.value as 'approved' | 'prohibited')}
            >
              <option value="prohibited">Prohibited</option>
              <option value="approved">Approved</option>
            </select>
            <input
              className="input"
              placeholder="Suggested replacement"
              value={replacement}
              onChange={(e) => setReplacement(e.target.value)}
            />
          </div>
          <button
            className="btn-primary"
            disabled={busy || !term.trim()}
            onClick={() =>
              void run(
                () =>
                  api.addTerm({
                    term: term.trim(),
                    kind,
                    replacement: replacement.trim() || undefined,
                  }),
                'Term added.',
              ).then(() => {
                setTerm('')
                setReplacement('')
              })
            }
          >
            {busy ? <Spinner /> : null}
            Add term
          </button>
        </section>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="card p-4">
          <h3 className="mb-2 text-sm font-semibold text-red-800">Prohibited</h3>
          <ul className="space-y-1.5 text-sm">
            {prohibited.map((t) => (
              <li key={t.id} className="flex flex-wrap items-baseline gap-2">
                <span className="font-mono text-red-900">{t.term}</span>
                {t.replacement && (
                  <span className="text-xs text-gray-500">→ {t.replacement}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
        <section className="card p-4">
          <h3 className="mb-2 text-sm font-semibold text-brand-800">Approved</h3>
          <ul className="space-y-1.5 text-sm">
            {approved.map((t) => (
              <li key={t.id} className="font-mono text-brand-900">
                {t.term}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}

function FactsTab({
  profile,
  canEdit,
  busy,
  run,
}: {
  profile: BrandProfile
  canEdit: boolean
  busy: boolean
  run: RunFn
}) {
  const [key, setKey] = useState('')
  const [value, setValue] = useState('')
  const [unit, setUnit] = useState('')

  return (
    <div className="space-y-4">
      {canEdit && (
        <section className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Add an approved fact
          </h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <input
              className="input"
              placeholder="fact_key (e.g. pack_price)"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <input
              className="input"
              placeholder="Value"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <input
              className="input"
              placeholder="Unit (optional)"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            />
          </div>
          <button
            className="btn-primary"
            disabled={busy || !key.trim() || !value.trim()}
            onClick={() =>
              void run(
                () =>
                  api.addFact({
                    fact_key: key.trim(),
                    value: value.trim(),
                    unit: unit.trim() || undefined,
                  }),
                'Fact added.',
              ).then(() => {
                setKey('')
                setValue('')
                setUnit('')
              })
            }
          >
            {busy ? <Spinner /> : null}
            Add fact
          </button>
        </section>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-2">Fact</th>
              <th className="px-4 py-2">Value</th>
              <th className="px-4 py-2">Unit</th>
              <th className="px-4 py-2">Source passage</th>
            </tr>
          </thead>
          <tbody>
            {profile.facts.map((f) => (
              <tr key={f.id} className="border-t border-gray-100">
                <td className="px-4 py-2 font-mono text-xs">{f.fact_key}</td>
                <td className="px-4 py-2 font-semibold">{f.value}</td>
                <td className="px-4 py-2 text-gray-500">{f.unit ?? '—'}</td>
                <td className="px-4 py-2 text-gray-500">
                  {f.source_passage_id ? `#${f.source_passage_id}` : 'none'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function PaletteTab({
  profile,
  canEdit,
  busy,
  run,
}: {
  profile: BrandProfile
  canEdit: boolean
  busy: boolean
  run: RunFn
}) {
  const [name, setName] = useState('')
  const [hex, setHex] = useState('#1F5C3A')
  const [role, setRole] = useState('')

  return (
    <div className="space-y-4">
      {canEdit && (
        <section className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Add a palette colour
          </h2>
          <div className="grid gap-3 sm:grid-cols-4">
            <input
              className="input"
              placeholder="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="input font-mono"
              placeholder="#RRGGBB"
              value={hex}
              onChange={(e) => setHex(e.target.value)}
            />
            <input
              className="input"
              placeholder="Role (optional)"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            />
            <button
              className="btn-primary"
              disabled={busy || !name.trim() || !/^#[0-9a-fA-F]{6}$/.test(hex)}
              onClick={() =>
                void run(
                  () =>
                    api.addPalette({
                      name: name.trim(),
                      hex,
                      role: role.trim() || undefined,
                    }),
                  'Palette colour added.',
                ).then(() => {
                  setName('')
                  setRole('')
                })
              }
            >
              {busy ? <Spinner /> : null}
              Add colour
            </button>
          </div>
        </section>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {profile.palette.map((c) => (
          <div key={c.id} className="card overflow-hidden">
            <div className="h-20 w-full" style={{ backgroundColor: c.hex }} />
            <div className="p-3">
              <div className="text-sm font-semibold text-charcoal">{c.name}</div>
              <div className="font-mono text-xs text-gray-500">{c.hex}</div>
              {c.role && <div className="mt-0.5 text-xs text-gray-500">{c.role}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function VisualTab() {
  const [colors, setColors] = useState('#1F5C3A, #FF0000')
  const [textHex, setTextHex] = useState('#E8A33D')
  const [bgHex, setBgHex] = useState('#F5EFE3')
  const [result, setResult] = useState<VisualCheckResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const check = async () => {
    setBusy(true)
    setError(null)
    try {
      setResult(
        await api.visualCheck({
          hex_colors: colors
            .split(',')
            .map((c) => c.trim())
            .filter(Boolean),
          text_hex: textHex,
          background_hex: bgHex,
        }),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The visual check failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Palette and contrast check
        </h2>
        <p className="text-xs text-gray-500">
          Real CIE76 colour distance against the approved palette, and the WCAG 2.1 contrast
          formula. No OCR is used.
        </p>
        <div>
          <label className="label" htmlFor="colors">
            Colours used (comma separated hex)
          </label>
          <input
            id="colors"
            className="input font-mono"
            value={colors}
            onChange={(e) => setColors(e.target.value)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="textHex">
              Text colour
            </label>
            <input
              id="textHex"
              className="input font-mono"
              value={textHex}
              onChange={(e) => setTextHex(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="bgHex">
              Background colour
            </label>
            <input
              id="bgHex"
              className="input font-mono"
              value={bgHex}
              onChange={(e) => setBgHex(e.target.value)}
            />
          </div>
        </div>
        <button className="btn-primary" disabled={busy} onClick={() => void check()}>
          {busy ? <Spinner /> : null}
          Run visual check
        </button>
      </section>

      {error && <ErrorBanner message={error} />}

      {result && (
        <section className="space-y-3">
          {result.contrast_ratio !== null && (
            <div className="card p-4 text-sm">
              Contrast ratio:{' '}
              <strong className="font-semibold">{result.contrast_ratio}:1</strong>{' '}
              {result.contrast_ratio >= 4.5 ? (
                <span className="badge ml-2 bg-brand-100 text-brand-800">Passes WCAG AA</span>
              ) : (
                <span className="badge ml-2 bg-red-100 text-red-800">Below 4.5:1</span>
              )}
            </div>
          )}

          {result.palette_match.length > 0 && (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-4 py-2">Input</th>
                    <th className="px-4 py-2">Closest approved</th>
                    <th className="px-4 py-2">ΔE</th>
                    <th className="px-4 py-2">On brand</th>
                  </tr>
                </thead>
                <tbody>
                  {result.palette_match.map((m) => (
                    <tr key={m.input} className="border-t border-gray-100">
                      <td className="px-4 py-2 font-mono">{m.input}</td>
                      <td className="px-4 py-2">
                        {m.closest} <span className="font-mono text-xs text-gray-500">{m.closest_hex}</span>
                      </td>
                      <td className="px-4 py-2">{m.delta_e}</td>
                      <td className="px-4 py-2">
                        {m.on_brand ? (
                          <span className="badge bg-brand-100 text-brand-800">Yes</span>
                        ) : (
                          <span className="badge bg-red-100 text-red-800">No</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.issues.length === 0 ? (
            <div className="card p-4 text-sm text-brand-800">
              No visual issues found for these inputs.
            </div>
          ) : (
            result.issues.map((issue, i) => (
              <div key={i} className="card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`badge ${
                      issue.severity === 'high'
                        ? 'bg-red-100 text-red-800'
                        : issue.severity === 'medium'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-sky-100 text-sky-800'
                    }`}
                  >
                    {issue.severity}
                  </span>
                  <span className="text-sm font-semibold text-charcoal">{issue.rule}</span>
                </div>
                <p className="mt-1 text-sm text-gray-700">{issue.explanation}</p>
                {issue.suggestion && (
                  <p className="mt-1 text-xs text-gray-500">
                    Suggested: <span className="font-mono">{issue.suggestion}</span>
                  </p>
                )}
              </div>
            ))
          )}
        </section>
      )}
    </div>
  )
}
