import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../components/AuthContext'
import SendBackPanel from '../components/SendBackPanel'
import {
  Diff,
  ErrorBanner,
  EvidenceBadge,
  LoadingBlock,
  SeverityBadge,
  Spinner,
  StatusBadge,
} from '../components/ui'
import type { ContentDetail, Finding } from '../types'

interface Segment {
  text: string
  finding: Finding | null
}

/** Build non-overlapping highlight segments from the draft and its findings. */
function buildSegments(body: string, findings: Finding[]): Segment[] {
  const spans = findings
    .filter(
      (f) =>
        f.span_start !== null &&
        f.span_end !== null &&
        f.span_end > f.span_start &&
        f.span_end <= body.length,
    )
    .sort((a, b) => (a.span_start ?? 0) - (b.span_start ?? 0))

  const segments: Segment[] = []
  let cursor = 0
  for (const finding of spans) {
    const start = finding.span_start as number
    const end = finding.span_end as number
    if (start < cursor) continue // skip overlaps; the first one wins
    if (start > cursor) segments.push({ text: body.slice(cursor, start), finding: null })
    segments.push({ text: body.slice(start, end), finding })
    cursor = end
  }
  if (cursor < body.length) segments.push({ text: body.slice(cursor), finding: null })
  return segments
}

function FindingCard({
  finding,
  active,
  onFocus,
  onDecide,
  busy,
  canEdit,
}: {
  finding: Finding
  active: boolean
  onFocus: () => void
  onDecide: (decision: 'accepted' | 'edited' | 'rejected', editedText?: string) => void
  busy: boolean
  canEdit: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(finding.edited_text ?? finding.suggestion ?? '')

  const decided = finding.creator_decision !== 'pending'

  return (
    <article
      id={`finding-${finding.id}`}
      className={`card scroll-mt-24 p-4 transition-shadow ${
        active ? 'ring-2 ring-brand-600' : ''
      }`}
      onClick={onFocus}
    >
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={finding.severity} />
        <EvidenceBadge status={finding.evidence_status} />
        <span className="badge bg-gray-100 text-gray-600">{finding.category}</span>
        {finding.detector === 'llm' && (
          <span className="badge bg-indigo-50 text-indigo-700">AI</span>
        )}
        {decided && (
          <span className="badge bg-brand-100 text-brand-800">
            {finding.creator_decision}
          </span>
        )}
      </div>

      <h3 className="mt-2 text-sm font-semibold text-charcoal">{finding.rule}</h3>
      <p className="mt-1 text-sm text-gray-700">{finding.explanation}</p>
      <p className="mt-1 text-xs text-gray-500">
        Confidence: <strong className="font-semibold">{Math.round(finding.confidence * 100)}%</strong>
      </p>

      <div className="mt-3 rounded-lg bg-gray-50 p-2.5">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
          Affected text
        </div>
        <p className="mt-0.5 break-words font-mono text-[13px] text-charcoal">
          {finding.affected_text}
        </p>
      </div>

      <div className="mt-2 rounded-lg border border-brand-100 bg-brand-50/60 p-2.5">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-brand-700">
          Approved source
        </div>
        {finding.source_quote ? (
          <>
            <p className="mt-0.5 text-[13px] italic text-brand-900">
              “{finding.source_quote}”
            </p>
            <p className="mt-1 text-[11px] text-brand-700">{finding.source_title}</p>
          </>
        ) : (
          <p className="mt-0.5 text-[13px] font-medium text-purple-800">
            Needs human verification — no approved source supports this claim.
          </p>
        )}
      </div>

      {finding.suggestion && (
        <div className="mt-3">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
            Suggested fix
          </div>
          <Diff before={finding.affected_text} after={finding.edited_text ?? finding.suggestion} />
        </div>
      )}

      {editing && (
        <div className="mt-3">
          <label className="label" htmlFor={`edit-${finding.id}`}>
            Your replacement text
          </label>
          <textarea
            id={`edit-${finding.id}`}
            className="input min-h-[70px] font-mono text-[13px]"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="mt-2 flex gap-2">
            <button
              className="btn-primary text-xs"
              disabled={busy || !draft.trim()}
              onClick={() => {
                onDecide('edited', draft)
                setEditing(false)
              }}
            >
              Save edit
            </button>
            <button className="btn-ghost text-xs" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {canEdit && !editing && (
        <div className="mt-3">
          {decided ? (
            <div
              className={`flex flex-wrap items-center gap-2 rounded-lg border p-2.5 text-xs ${
                finding.creator_decision === 'rejected'
                  ? 'border-red-200 bg-red-50 text-red-900'
                  : 'border-brand-200 bg-brand-50 text-brand-900'
              }`}
            >
              <span className="font-semibold">
                {finding.creator_decision === 'accepted' && '✓ Fix accepted'}
                {finding.creator_decision === 'edited' && '✓ Your edit saved'}
                {finding.creator_decision === 'rejected' && '✕ Fix rejected'}
              </span>
              <span className="text-[11px] opacity-80">
                {finding.creator_decision === 'rejected'
                  ? 'This issue will stay in the draft.'
                  : 'Applied when you create the revised draft.'}
              </span>
              <div className="ml-auto flex gap-1.5">
                <button
                  className="btn-secondary px-2 py-1 text-[11px]"
                  disabled={busy}
                  onClick={() => setEditing(true)}
                >
                  Change
                </button>
                <button
                  className="btn-ghost px-2 py-1 text-[11px]"
                  disabled={busy}
                  onClick={() => onDecide('pending' as never)}
                >
                  Undo
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <button
                className="btn-primary text-xs"
                disabled={busy || !finding.suggestion}
                title={finding.suggestion ? undefined : 'No automatic fix — use Edit'}
                onClick={() => onDecide('accepted')}
              >
                {busy ? <Spinner className="h-3 w-3" /> : null}
                Accept fix
              </button>
              <button
                className="btn-secondary text-xs"
                disabled={busy}
                onClick={() => setEditing(true)}
              >
                Edit
              </button>
              <button
                className="btn-ghost text-xs text-red-700 hover:bg-red-50"
                disabled={busy}
                onClick={() => onDecide('rejected')}
              >
                Reject
              </button>
            </div>
          )}
        </div>
      )}
    </article>
  )
}

export default function ReviewScreen() {
  const { id } = useParams()
  const itemId = Number(id)
  const navigate = useNavigate()
  const { me } = useAuth()

  const [item, setItem] = useState<ContentDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [editingDraft, setEditingDraft] = useState(false)
  const [draftText, setDraftText] = useState('')
  const [editNote, setEditNote] = useState('')
  const draftRef = useRef<HTMLDivElement>(null)

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

  const findings = item?.findings ?? []
  const body = item?.current_version?.body ?? ''
  const segments = useMemo(() => buildSegments(body, findings), [body, findings])

  const decidedCount = findings.filter((f) => f.creator_decision !== 'pending').length
  const openHigh = findings.filter(
    (f) => f.severity === 'high' && (f.creator_decision === 'pending' || f.creator_decision === 'rejected'),
  ).length

  const act = async (label: string, fn: () => Promise<ContentDetail>) => {
    setBusy(label)
    setError(null)
    try {
      setItem(await fn())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That action failed.')
    } finally {
      setBusy(null)
    }
  }

  const focusFinding = (findingId: number) => {
    setActiveId(findingId)
    document.getElementById(`finding-${findingId}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
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

  if (!item) return <LoadingBlock label="Loading the review…" />

  const run = item.review_run
  const version = item.current_version
  const status = version?.status ?? item.status

  // --- who is this version waiting on, and what can I do about it? ---------
  const waitingOnManager = status === 'Manager Review' || status === 'Resubmitted'
  const waitingOnApprover = status === 'Approver Review'
  const isFinal = status === 'Approved' || status === 'Rejected'
  const canSendOn = status === 'Draft' || status === 'AI Review Complete' || status === 'Changes Required'

  const isManager = me?.role === 'manager' || me?.role === 'admin'
  const isApprover = me?.role === 'approver' || me?.role === 'admin'
  const returnToManagerPrefix = 'Sent back to the manager: '
  const returnToCreatorPrefix = 'Sent back to the creator: '
  const returnNoteTarget =
    status === 'Manager Review'
      ? 'manager'
      : status === 'Changes Required'
        ? 'creator'
        : null
  const returnNotePrefix =
    returnNoteTarget === 'manager'
      ? returnToManagerPrefix
      : returnNoteTarget === 'creator'
        ? returnToCreatorPrefix
        : null
  const canViewReturnNote =
    (returnNoteTarget === 'manager' && isManager) ||
    (returnNoteTarget === 'creator' && me?.role === 'creator')
  const returnNotes =
    canViewReturnNote && returnNotePrefix
      ? item.comments.filter((comment) => comment.body.startsWith(returnNotePrefix))
      : []

  // Acting on findings is only allowed when the version is actually waiting on
  // you. Otherwise the buttons would contradict the "waiting on X" banner.
  const myTurn =
    (isApprover && waitingOnApprover) ||
    (isManager && waitingOnManager) ||
    (!isManager && !isApprover && canSendOn)

  const canEdit = myTurn
  const canEditDraft = myTurn

  // Who can send this version back one level, and to whom.
  const sendBackTo =
    isApprover && waitingOnApprover
      ? 'Manager'
      : isManager && (waitingOnManager || canSendOn)
        ? 'Creator'
        : null

  // The single forward action, named for its actual destination.
  let forward: { label: string; to: string; enabled: boolean; hint: string } | null = null
  if (isManager && (waitingOnManager || canSendOn)) {
    forward = {
      label: 'Send to Approver',
      to: 'Rohan Iyer (Approver)',
      enabled: version?.review_state === 'reviewed',
      hint:
        version?.review_state === 'reviewed'
          ? 'The approver makes the final decision.'
          : 'Run the brand check first.',
    }
  } else if (isApprover && canSendOn) {
    // The approver revised this version themselves, so it needs manager
    // re-review before it can be approved again.
    forward = {
      label: 'Return to Manager',
      to: 'Arun Mehta (Manager)',
      enabled: version?.review_state === 'reviewed',
      hint:
        version?.review_state === 'reviewed'
          ? 'You changed this version, so it needs manager re-review before approval.'
          : 'Run the brand check first.',
    }
  } else if (!isManager && !isApprover && canSendOn) {
    forward = {
      label: 'Send to Manager',
      to: 'Arun Mehta (Manager)',
      enabled: version?.review_state === 'reviewed',
      hint:
        version?.review_state === 'reviewed'
          ? 'The manager reviews before it reaches the approver.'
          : 'Run the brand check first.',
    }
  }

  const waitingLabel = waitingOnApprover
    ? 'Waiting on Rohan Iyer (Approver)'
    : waitingOnManager
      ? 'Waiting on Arun Mehta (Manager)'
      : isFinal
        ? `Final decision: ${status}`
        : 'Not yet sent for review'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to="/dashboard" className="text-xs font-semibold text-brand-700 hover:underline">
            ← Dashboard
          </Link>
          <h1 className="mt-1 truncate text-2xl font-bold tracking-tight text-brand-900">
            {item.title}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-600">
            <StatusBadge status={item.status} />
            <span>v{version?.version_no}</span>
            <span>·</span>
            <span>{item.content_type}</span>
            <span>·</span>
            <span>{findings.length} findings</span>
          </div>
        </div>
      </div>

      {/* --- where the version is right now --- */}
      <div
        className={`flex flex-wrap items-center gap-2 rounded-lg border p-3 text-sm ${
          isFinal
            ? 'border-brand-200 bg-brand-50 text-brand-900'
            : waitingOnApprover
              ? 'border-purple-200 bg-purple-50 text-purple-900'
              : waitingOnManager
                ? 'border-indigo-200 bg-indigo-50 text-indigo-900'
                : 'border-gray-200 bg-gray-50 text-gray-700'
        }`}
        role="status"
      >
        <svg
          className="h-4 w-4 shrink-0"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
        <span className="font-semibold">{waitingLabel}</span>
        {isFinal && (
          <span className="text-xs opacity-80">
            Any edit creates a new version and reopens the review.
          </span>
        )}
      </div>

      {returnNotes.length > 0 && returnNotePrefix && (
        <section
          aria-labelledby="return-notes-title"
          className="card border-amber-200 bg-amber-50/60 p-4"
        >
          <h2
            id="return-notes-title"
            className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-900"
          >
            {returnNoteTarget === 'manager'
              ? 'Came back for re-review'
              : 'Sent back for changes'}
          </h2>
          <ul className="space-y-2">
            {returnNotes.map((comment) => (
              <li key={comment.id} className="rounded-lg border border-amber-200 bg-white/70 p-3">
                <div className="text-xs font-semibold text-amber-900">{comment.author}</div>
                <p className="mt-1 whitespace-pre-wrap text-sm text-amber-950">
                  {comment.body.slice(returnNotePrefix.length)}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* --- actions, grouped and named by destination --- */}
      <div className="card space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            className="btn-secondary text-xs"
            disabled={busy !== null}
            onClick={() => void act('review', () => api.review(itemId))}
          >
            {busy === 'review' ? <Spinner className="h-3 w-3" /> : null}
            Re-run brand check
          </button>
          <button
            className="btn-secondary text-xs"
            disabled={busy !== null || decidedCount === 0}
            title={decidedCount === 0 ? 'Accept or edit at least one finding first' : undefined}
            onClick={() => void act('revise', () => api.revise(itemId))}
          >
            {busy === 'revise' ? <Spinner className="h-3 w-3" /> : null}
            Apply accepted fixes → new version
          </button>
        </div>

        {forward && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-brand-200 bg-brand-50/60 p-3">
            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-brand-700">
                Next step
              </div>
              <div className="text-sm text-brand-900">
                Send this version to <strong className="font-semibold">{forward.to}</strong>
              </div>
              <div className="text-[11px] text-brand-700">{forward.hint}</div>
            </div>
            <button
              className="btn-primary shrink-0"
              disabled={busy !== null || !forward.enabled}
              onClick={() => void act('submit', () => api.submit(itemId))}
            >
              {busy === 'submit' ? <Spinner /> : null}
              {forward.label}
            </button>
          </div>
        )}

        {sendBackTo && (
          <SendBackPanel
            destination={sendBackTo}
            busy={busy !== null}
            onSendBack={(note) => act('send-back', () => api.sendBack(itemId, note))}
          />
        )}

        {isApprover && waitingOnApprover && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-purple-200 bg-purple-50 p-3">
            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-purple-700">
                Your decision
              </div>
              <div className="text-sm text-purple-900">
                This version is waiting on you. Approve it, or send it back to the creator.
              </div>
            </div>
            <Link to={`/approval/${itemId}`} className="btn-primary shrink-0">
              Open approval decision →
            </Link>
          </div>
        )}

        {!forward && !(isApprover && waitingOnApprover) && (
          <p className="text-xs text-gray-500">
            {isFinal
              ? 'This version has a final decision. Edit the draft to start a new version.'
              : waitingOnApprover
                ? 'Waiting on the approver. You cannot act on this version.'
                : waitingOnManager
                  ? 'Waiting on the manager. You cannot act on this version.'
                  : 'Nothing to send yet.'}
          </p>
        )}
      </div>

      {error && <ErrorBanner message={error} />}

      {run && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            run.llm_status === 'ok'
              ? 'border-brand-200 bg-brand-50 text-brand-900'
              : 'border-amber-200 bg-amber-50 text-amber-900'
          }`}
          role="status"
        >
          <strong className="font-semibold">
            {run.llm_status === 'ok' ? 'AI analysis completed.' : 'Deterministic checks only.'}
          </strong>{' '}
          {run.llm_message} ({run.deterministic_count} rule-based, {run.llm_count} AI,{' '}
          {run.duration_ms} ms)
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        {/* --- draft with highlights --- */}
        <section className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Draft v{version?.version_no}
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">
                {decidedCount}/{findings.length} decided
              </span>
              {canEditDraft && !editingDraft && (
                <button
                  className="btn-secondary px-2 py-1 text-[11px]"
                  onClick={() => {
                    setDraftText(body)
                    setEditNote('')
                    setEditingDraft(true)
                  }}
                >
                  Edit draft text
                </button>
              )}
            </div>
          </div>

          {editingDraft ? (
            <div className="space-y-2">
              <textarea
                className="input min-h-[320px] font-mono text-[13px] leading-relaxed"
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                aria-label="Edit the draft text"
              />
              <input
                className="input text-xs"
                placeholder="Why are you editing? (optional, recorded in the audit trail)"
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
                maxLength={500}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-primary text-xs"
                  disabled={busy !== null || !draftText.trim() || draftText === body}
                  onClick={async () => {
                    await act('edit-draft', () =>
                      api.editDraft(itemId, draftText, editNote.trim() || undefined),
                    )
                    setEditingDraft(false)
                  }}
                >
                  {busy === 'edit-draft' ? <Spinner className="h-3 w-3" /> : null}
                  Save as new version
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setEditingDraft(false)}
                  disabled={busy !== null}
                >
                  Cancel
                </button>
                <span className="self-center text-[11px] text-gray-500">
                  Saving creates a new version and resets the review.
                </span>
              </div>
            </div>
          ) : (
            <>
              <div
                ref={draftRef}
                className="max-h-[70vh] overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-brand-100 bg-white p-4 text-[15px] leading-relaxed"
              >
                {segments.map((seg, i) =>
                  seg.finding ? (
                    <mark
                      key={i}
                      className={`hl hl-${seg.finding.severity} ${
                        activeId === seg.finding.id ? 'hl-active' : ''
                      } ${seg.finding.creator_decision !== 'pending' ? 'hl-resolved' : ''}`}
                      onClick={() => focusFinding(seg.finding!.id)}
                      title={seg.finding.rule}
                    >
                      {seg.text}
                    </mark>
                  ) : (
                    <span key={i}>{seg.text}</span>
                  ),
                )}
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Click a highlight to jump to its finding. Green highlights are already decided.
              </p>
            </>
          )}
        </section>

        {/* --- findings --- */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Findings
            </h2>
            {openHigh > 0 && (
              <span className="badge bg-red-100 text-red-800">{openHigh} high open</span>
            )}
          </div>

          {findings.length === 0 ? (
            <div className="card p-6 text-center text-sm text-gray-600">
              No issues found in this version. You can submit it for approval.
            </div>
          ) : (
            <div className="max-h-[70vh] space-y-3 overflow-y-auto pr-1">
              {findings.map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  active={activeId === f.id}
                  busy={busy !== null}
                  canEdit={canEdit}
                  onFocus={() => setActiveId(f.id)}
                  onDecide={(decision, editedText) =>
                    void act(`finding-${f.id}`, () =>
                      api.decideFinding(itemId, f.id, decision, editedText),
                    )
                  }
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link to={`/approval/${itemId}`} className="btn-secondary">
          Open approval view →
        </Link>
        {me?.role === 'approver' && (
          <Link to={`/history/${itemId}`} className="btn-ghost">
            View past changes
          </Link>
        )}
        <button className="btn-ghost ml-auto" onClick={() => navigate('/dashboard')}>
          Done
        </button>
      </div>
    </div>
  )
}
