# COMPLETED_FEATURES

An honest list of what works, what is partial, and what is not built.

The 46-test local suite and frontend production build were last verified:
2026-11-20. The deployed health endpoint was last checked on 2026-11-18 and
has not been rechecked after the recent local changes.

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

### Business authentication
- Supabase access tokens are verified against the project issuer/JWKS.
- Protected API requests resolve the Supabase subject to an active workspace membership;
  role authorization comes from the membership database row.
- Workspace admins can invite employees, assign/update roles and deactivate/reactivate accounts.
- Verified users can create an organization when enabled; organization admins can add brand workspaces.
- Members can switch between only the brand workspaces they are authorized to access.
- Password recovery and invitation password setup use Supabase's email links.
- Demo role selection is disabled by default in code and can be enabled explicitly for local demos.

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
- Create, edit, disable and version structured policy rules with content applicability and effective dates.
- AI policy findings retain the cited rule version and text; invalid/inactive rule citations require verification.
- Upload a guideline PDF → ingested into approved passages, one chunk per page.

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
- Review assignment and due-date API.
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
| **Authentication and tenancy** | Supabase email/password sign-in, recovery, invitations, organization onboarding and brand workspace switching are implemented but need customer Supabase configuration and live end-to-end verification. Demo role selection is disabled by default in code and should stay off in production. |
| **OCR** | Not implemented. Scanned PDFs are rejected with a clear message. |
| **Deployment** | Public frontend and API are deployed. Health checks passed on 2026-11-18; current local changes are not yet deployed. |
| **Assignment UI** | Assignment and due-date API exists; a reviewer assignment form is not yet surfaced in the submission UI. |
| **API-key integration** | Key creation/listing exists, but API-key authentication and revocation are not yet implemented. |
| **Evaluation** | Synthetic fixtures test regression only. A reviewed real-world labelled corpus and precision/recall by category are not available. |

---

## Partially credential-dependent

- Analytics and audit export are implemented locally.
- SMTP and signed webhook delivery require production credentials/endpoints and live end-to-end testing.
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
