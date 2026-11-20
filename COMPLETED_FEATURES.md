# COMPLETED_FEATURES

An honest list of what works, what is partial, and what is not built.

The 53-test local suite and frontend production build were verified on
2026-11-21. The deployed API health endpoint was last checked on 2026-11-18;
the current local profile-management changes still need deployment and a live
end-to-end check.

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

### Demo access and backend identity
- The public web app offers Creator, Manager and Approver demo roles without an
  employee sign-in or password flow.
- Demo sessions expire after 12 hours by default and are rejected after logout.
- Backend Supabase token verification, organization creation and member administration
  remain available for server-side integrations; there is no browser sign-in UI for them.

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
- Managers can add, edit and delete terms, facts and palette colours; changes
  are workspace-scoped and recorded in the audit trail.
- Approved facts can cite an approved passage from the same workspace.
- Download the original private PDF source from uploaded guideline passages.
- Manual passages correctly show that no source file is available.
- Create, edit, disable and version structured policy rules with content applicability and effective dates.
- AI policy findings retain the cited rule version and text; invalid/inactive rule citations require verification.
- Upload a text-based guideline PDF → ingested into approved passages, one chunk per page.

### Visual checks
- Palette similarity using real CIE76 colour distance.
- WCAG 2.1 contrast ratio calculation.
- Verified: off-palette colours and low-contrast pairs are flagged with numbers.
- Upload PNG, JPEG or WebP assets (10 MB/20 megapixel limit) for dominant-colour
  sampling against the configured brand palette.
- The image check does not claim OCR, logo detection, typography detection, or
  text/background contrast from arbitrary image pixels; these need human review.

### Storage and operations
- Original content uploads and guideline PDFs persist in private local storage
  or configured S3-compatible storage, with workspace-checked download routes.
- Workspace analytics and audit CSV export.
- Managers can assign active reviewers and set deadlines from a submission's
  review page; assignments and due dates also appear on dashboard cards.
- API-key creation stores only hashes; newly created keys are currently
  intended as credentials for future integration work until key authentication
  and revocation are wired in.
- Signed webhook outbox and SMTP notification outbox with retry attempts; live
  delivery requires external configuration and has not been verified here.
- Basic usage events are recorded for submissions, reviews, and approvals.
- A small synthetic deterministic regression harness is provided; it is not an
  accuracy benchmark.

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
| **Backend organization/member integrations** | Supabase token verification and admin APIs remain in the backend but are not exposed through the public demo's browser UI; a customer-facing sign-in experience is not included. |
| **OCR** | Not implemented. Scanned PDFs are rejected with a clear message. |
| **Deployment** | Public frontend and API are deployed. Recheck API health and run the complete workflow after deploying the current local changes. |
| **API-key integration** | Key creation/listing exists, but API-key authentication and revocation are not yet implemented. |
| **Evaluation** | Synthetic fixtures test regression only. A reviewed real-world labelled corpus and precision/recall by category are not available. |

---

## Partially credential-dependent

- Analytics and audit export are implemented locally.
- SMTP and signed webhook delivery require production credentials/endpoints and live end-to-end testing.
- Assignment notification emails are queued when an assigned submission is sent for review; delivery depends on SMTP configuration.
- Private S3-compatible storage requires a configured bucket and credentials; the local backend has not been configured against production storage.
- Live image OCR/logo/typeface recognition is not enabled; image colour checks and
  manual-review limitations are implemented.
- Real publishing integration (by design — approval is terminal).
- Competitor mention detection beyond the prohibited-terms list.
- Hybrid/vector retrieval, calibrated confidence scoring and cross-document
  contradiction detection; these need a labelled evaluation set before they
  can be validated or claimed as product capabilities.
- Broader policy-change approval/governance and deterministic evaluation of
  configurable policy rules are not complete; rules currently inform AI review.

---

## Accuracy claims

**No real-world accuracy numbers are claimed.** A small synthetic deterministic
regression harness is available at `scripts/evaluate_brandshield.py`; it
explicitly labels output as regression-only and does not measure real-world
precision or recall.
