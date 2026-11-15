import { useState } from 'react'
import { Spinner } from './ui'

/**
 * Sends a version back one level. The note is mandatory, both here and on the
 * server, so the previous level always knows why it came back.
 */
export default function SendBackPanel({
  destination,
  busy,
  onSendBack,
}: {
  destination: string
  busy: boolean
  onSendBack: (note: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')

  const submit = async () => {
    if (!note.trim()) return
    await onSendBack(note.trim())
    setNote('')
    setOpen(false)
  }

  if (!open) {
    return (
      <button
        type="button"
        className="btn-secondary text-xs text-amber-800"
        disabled={busy}
        onClick={() => setOpen(true)}
      >
        Send back to {destination}
      </button>
    )
  }

  return (
    <div className="w-full rounded-lg border border-amber-300 bg-amber-50 p-3">
      <label className="label text-amber-900" htmlFor="send-back-note">
        Why is this going back to {destination}? (required)
      </label>
      <textarea
        id="send-back-note"
        className="input min-h-[70px]"
        value={note}
        maxLength={2000}
        placeholder="Explain what needs to change before this can move forward…"
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn-primary text-xs"
          disabled={busy || !note.trim()}
          onClick={() => void submit()}
        >
          {busy ? <Spinner className="h-3 w-3" /> : null}
          Send back with note
        </button>
        <button
          type="button"
          className="btn-ghost text-xs"
          disabled={busy}
          onClick={() => {
            setOpen(false)
            setNote('')
          }}
        >
          Cancel
        </button>
        {!note.trim() && (
          <span className="text-[11px] text-amber-800">A note is required.</span>
        )}
      </div>
    </div>
  )
}
