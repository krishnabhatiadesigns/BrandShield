# CHANGES_FROM_PLAN

What changed from the Round 1 plan and why.

---

## 1. Database: SQLite locally, generic PostgreSQL option

**Planned:** Hosted PostgreSQL from day one.

**Changed:** Built against a local SQLite file, with a database layer that speaks
both engines.

**Why:** Rather than block the workflow on hosted database setup, `app/db.py` was written to translate `?`
placeholders to `%s` and return dicts from either driver. The schema is one DDL
template rendered per engine. Switching from SQLite to generic PostgreSQL is a
`DATABASE_URL` change, not a code change.

**Impact:** The core workflow is verifiable end to end. Provider-specific auth
and storage are not part of this product; uploads are parsed in memory.

---

## 2. Added a distinct `Approver Review` status

**Planned:** `Manager Review` covered both manager and approver.

**Changed:** Added `Approver Review` as its own status.

**Why:** With one shared status, every role saw the same "Submit for approval"
button and clicking it in the wrong state returned a 403 that the UI swallowed.
The server log showed five consecutive 403s from a user clicking a dead button.

**Impact:** Each role now has exactly one forward action, named for its
destination ("Send to Manager" / "Send to Approver"). The approver has no forward
button at all.

---

## 3. Separation of duties: reviewers cannot author

**Planned:** `creator`, `manager` and `admin` could all create submissions.

**Changed:** Only `creator` and `admin` can create.

**Why:** A manager could author a draft and then approve their own work, which
defeats the purpose of the review chain.

**Impact:** Enforced in the backend and reflected in the UI (nav link hidden,
dashboard button replaced with a notice, direct URL blocked).

---

## 4. Approver can act on findings

**Planned:** Accept/Edit/Reject was creator and manager only.

**Changed:** The approver can also accept, edit and reject findings, re-run the
check, and revise the draft.

**Why:** The approver is the last line of defence and most needs to act on what
the AI flagged. Excluding them made the role read-only apart from a binary
approve/reject.

**Impact:** Added a "Return to Manager" path — if the approver revises the draft,
the new version goes back for manager re-review, because a new version
invalidates the old approval.

---

## 5. Re-running a check no longer resets the workflow

**Planned:** A check run set the version to `AI Review Complete`.

**Changed:** A re-run preserves the current status and prior decisions.

**Why:** An approver who clicked "Re-run brand check" was silently dropped out of
`Approver Review`, losing their turn and all their decisions.

**Impact:** Re-run is now an analysis refresh. A brand-new draft still advances to
`AI Review Complete` on its first check.

---

## 6. Suggestion contract made explicit

**Planned:** Suggestions were free text.

**Changed:** `suggestion` must replace exactly `[span_start, span_end)`.

**Why:** Early suggestions were full sentences while spans were single words,
which produced duplicated text like "our bars are the Made with oats… cheapest
oat bar wholesome snack".

**Impact:** The revise step now skips overlapping spans and verifies the stored
span still matches the text before applying. Prohibited-term replacements absorb
a preceding article so "We're the #1" becomes "We're a leading", not "We're the a
leading".

---

## 7. OCR dropped

**Planned:** OCR "only if it works reliably".

**Changed:** Not implemented.

**Why:** Reliable OCR needs a heavy dependency and tuning. A wrong OCR result is
worse than an honest refusal.

**Impact:** Scanned PDFs are rejected with a clear message instead of silently
returning nothing.

---

## 8. Local embeddings dropped

**Planned:** "optional local embeddings only if time allows".

**Changed:** BM25 only.

**Why:** Groq has no embeddings endpoint, and BM25 was sufficient for the
demo-sized corpus.

---

## 9. Visual checks: hex input, not image upload

**Planned:** Image upload with palette and contrast checks.

**Changed:** The visual check accepts hex colours directly.

**Why:** Pixel sampling from an arbitrary image needs cropping and region
selection to be meaningful. The colour maths (CIE76 ΔE, WCAG contrast) is real
and verified; the input path is simpler.

---

## 10. Labelled accuracy evaluation not completed

**Planned:** A 20-item labelled set with precision and recall printed to markdown,
plus cross-workspace isolation and approval-invalidation tests.

**Changed:** The labelled 20-item accuracy set and precision/recall report are
still not written. Round 3 added regression and workflow tests in
`backend/tests/test_round3_readiness.py` and `backend/tests/test_sessions.py`,
bringing the automated backend suite to 20 tests.

**Why:** Functional correctness tests and accuracy measurement answer different
questions. No labelled dataset was available to support an accuracy claim.

**Impact:** **No accuracy numbers are claimed anywhere in this repo.** Evidence
validation, review transitions, stale/overlapping edits and approval invalidation
are now exercised by automated tests.

---

## 11. Demo session and CORS hardening

**Changed:** Removed the unused provider-specific auth/storage configuration.
Demo tokens now expire, can be revoked on logout, and are rejected after expiry.
Wildcard CORS origins are rejected in favor of exact configured origins.

**Why:** The running application provides demo role selection rather than a
production account system, and it does not persist uploaded files. Configuration
and documentation should describe the behavior that actually exists.

**Impact:** Tests cover expiration, revocation, explicit CORS origins and
workspace-scoped approved/in-force retrieval. Production deployment must set
`CORS_ORIGINS` to the frontend's exact origin.

---

## 12. Deployment completed

**Planned:** Public URL on Vercel/Netlify + Render/Railway.

**Changed:** The frontend is deployed on Vercel and the API on Azure App Service.

**Verified:** The frontend loaded and the API `/health` endpoint reported
`status: ok` and `database: up` on 18 November 2026.

**Impact:** Judges can use the live demo without a local setup. After any
deployment or configuration change, repeat the health check and the main workflow.
