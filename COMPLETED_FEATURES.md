# COMPLETED_FEATURES

An honest list of what works, what is partial, and what is not built.

Last verified: 2026-11-18 against the local test suite and deployed health endpoint.

---

## ✅ Works (verified end to end)

### Core workflow
- **Submit** pasted text, or upload PDF / DOCX / TXT.
- **Deterministic checks** run with no network: prohibited terms, wrong product
  names, required disclaimers by content type, banned phrases, all-caps,
  exclamation marks, emoji count, exact fact mismatches (protein, price, launch
  date, certifications), unsupported ranking claims.
- **BM25 retrieval** over approved, in-force passages, workspace-filtered in SQL
  before ranking.
- **Groq LLM analysis** in JSON mode, server-side only. Verified live:
  `AI analysis completed. (3 rule-based, 2 AI, 3621 ms)`.
- **Validation layer** discards or downgrades any finding whose cited passage is
  missing, unapproved, out of force, or from another workspace.
- **Findings** show exact text, rule, explanation, cited source quote, and a
  before/after diff.
- **Accept / Edit / Reject** per finding, with a confirmation bar and Undo.
- **Apply accepted fixes** creates a new version (never a silent rewrite).
- **Direct draft editing** for creator, manager and approver.
- **Versioning**: every edit creates a new version and resets review state.
- **Approval** tied to one exact version, with required reason for send-back and
  reject, and explicit sign-off for unresolved high-severity items.

### Roles
- Creator → Manager → Approver chain with a distinct `Approver Review` status.
- Role enforcement in the backend (`require_role`), not only the UI.
- Managers and approvers **cannot** create submissions (separation of duties).
- Only the approver can make the final decision.
- Turn-aware UI: action buttons only appear when the version is waiting on you.

### Resilience
- If the LLM fails, times out or is unconfigured, deterministic findings still
  return and the UI states exactly what happened.
- Demo sessions expire after 12 hours by default; logout revokes the session
  server-side. CORS rejects wildcard origins.
- Re-running a check preserves workflow status and prior decisions.
- `/health` endpoint for keep-warm pings; the frontend shows "waking up the
  server" while polling it.
- Loading states on every async action; friendly error banners with retry.

### Brand profile
- View guidelines, passages, approved/prohibited terms, facts, palette.
- Add terms, facts, palette colours and passages (manager/admin).
- Upload a guideline PDF → ingested into approved passages, one chunk per page.

### Visual checks
- Palette similarity using real CIE76 colour distance.
- WCAG 2.1 contrast ratio calculation.
- Verified: off-palette colours and low-contrast pairs are flagged with numbers.

### Other
- Audit trail for every submission, decision, comment and approval.
- Version history per submission.
- Comments on a version.
- Mobile-responsive layout (verified at 390×844 and 1280×900).
- Workflow diagram on the landing page.
- Help dialog explaining the workflow and differentiators.

---

## ⚠️ Partial

| Feature | Limitation |
|---|---|
| **Decision preservation on re-run** | Decisions survive only for findings that reappear identically (same rule + span). If the LLM rewords a finding, it returns as `pending`. Deterministic findings are stable and always keep decisions. |
| **Authentication** | The demo lets visitors select a role; there is no persistent real-user account lifecycle. Do not use it to protect confidential production data. |
| **Guideline upload persistence** | Files are parsed in memory and are not persisted to object storage. |
| **Image upload** | Visual checks accept hex colours, not image files. No pixel sampling from an uploaded image. |
| **OCR** | Not implemented. Scanned PDFs are rejected with a clear message. |
| **Deployment** | Public frontend and API are deployed. Health checks passed on 2026-11-18; retest both after any deployment/configuration change. |
| **Test suite** | 20 automated backend tests cover regression, workflow, session and retrieval behavior. The planned 20-item labelled accuracy set and precision/recall report are **not** written. |

---

## ❌ Not built

- Analytics dashboard.
- Email notifications.
- Multi-workspace UI (the data model supports it; the UI is single-workspace).
- Real publishing integration (by design — approval is terminal).
- Competitor mention detection beyond the prohibited-terms list.
- Hybrid/vector retrieval, calibrated confidence scoring and cross-document
  contradiction detection; these need a labelled evaluation set before they
  can be validated or claimed as product capabilities.

---

## Accuracy claims

**No accuracy numbers are claimed.** The 20-item labelled evaluation set described
in the plan was not completed, so precision and recall are unmeasured. Any
statement about detection quality in this repo is qualitative only.
