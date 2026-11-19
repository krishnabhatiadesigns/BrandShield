# BrandShield AI

Brand governance for content **before** it is published. Submit a draft, get
evidence-backed findings, fix them, and route that exact version to a human
approver. Nothing is auto-published and nothing is silently rewritten.

> **Live demo:** [Open BrandShield](https://brand-shield-amber.vercel.app/).
> The frontend uses the deployed API listed under [Deployment](#deployment).
>
> **Round 3 submission:** See [the complete submission packet](./SUBMISSION.md)
> and [download the product PDF](./BrandShield_Product.pdf).

---

## What it does

A creator submits content (social post, ad, email or document). BrandShield AI
checks it against the organisation's approved brand guidelines, approved facts,
terminology and visual identity. Every issue comes back with:

- the **exact affected text**
- the **rule** it breaks
- **why it matters**
- the **cited approved source**, or "Needs human verification" if no evidence exists
- a **suggested correction**

The creator accepts, edits or rejects each fix. A manager reviews, then an
approver approves or rejects that specific version.

---

## Quick start

### Prerequisites

- Python 3.13 (the version used for verification)
- Node.js 18 or newer and npm

Clone the repository and open a PowerShell terminal at its root:

```powershell
git clone https://github.com/krishnabhatiadesigns/BrandShield.git
cd BrandShield
Copy-Item .env.example .env
```

The `.env` file is optional for local use. Leave `GROQ_API_KEY` blank to run
deterministic checks without external AI calls. The demo has role-selectable
sessions, not real user accounts; use fictional/sample data only.

### 1. Backend

```powershell
Set-Location backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The database is created and seeded automatically on first start.

- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 2. Frontend

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open http://localhost:5173 and click **Try as Creator**.

---

## Environment variables

Copy `.env.example` to `.env` in the repo root. `.env` is gitignored.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | no | Generic PostgreSQL connection URL. Blank = local SQLite file. |
| `GROQ_API_KEY` | no | Enables AI analysis. Without it, deterministic checks still run. |
| `GROQ_MODEL` | no | Defaults to `openai/gpt-oss-120b`. |
| `LLM_TIMEOUT_SECONDS` | no | Defaults to 25. |
| `CORS_ORIGINS` | no | Comma-separated exact allowed origins; `*` is rejected. |
| `DEMO_WORKSPACE_SLUG` | no | Defaults to `northwind-foods`. |
| `DEMO_SESSION_TTL_HOURS` | no | Demo-session lifetime; defaults to 12 hours. |
| `SEED_ON_START` | no | Defaults to `true`. |

**No secrets are committed.** `.env` is in `.gitignore` and was verified with
`git check-ignore`.

---

## Architecture

```mermaid
flowchart TB
    subgraph Browser
        UI[React + Vite + Tailwind]
    end

    subgraph Server["FastAPI (server-side only)"]
        API[Routers<br/>session · content · brand · visual]
        AUTH[Auth + role enforcement]
        PIPE[Review pipeline]
        DET[Deterministic checks]
        RET[BM25 retrieval]
        LLM[Groq client]
        VAL[Validation layer]
    end

    subgraph Data
        DB[(SQLite / PostgreSQL)]
    end

    UI -->|X-Demo-Token| API
    API --> AUTH
    AUTH --> DB
    API --> PIPE
    PIPE --> DET
    PIPE --> RET
    PIPE --> LLM
    LLM -->|JSON findings| VAL
    DET --> VAL
    VAL --> DB
    RET --> DB
```

### Review pipeline

1. **Extract** text and split into sentence spans with character offsets.
2. **Deterministic checks** (pure Python, no network): prohibited terms, wrong
   product names, required disclaimers, banned phrases, exact fact mismatches
   (protein, price, launch date, certifications), unsupported ranking claims.
3. **Retrieval**: BM25 over approved, in-force passages, filtered by workspace
   *before* ranking.
4. **LLM analysis** (Groq, JSON mode): tone, messaging and claim support.
5. **Validation**: every LLM finding is checked — the cited passage must exist,
   be approved, be in force and belong to the same workspace. Affected text must
   actually appear in the draft. Unsupported claims are never called "false".
6. **Merge**, de-duplicate, sort by severity, store.

If the LLM fails or times out, steps 2, 3 and 6 still run and the UI says so.

---

## Demo script (under 2 minutes)

1. Open the landing page → click **Try as Creator**.
2. Click **New submission** → load the **LinkedIn launch post** sample.
3. Press **Run review**. You get 8 findings, each with a cited source.
4. Click a highlight in the draft to jump to its finding.
5. Click **Accept fix** on two or three findings — note the confirmation bar.
6. Press **Apply accepted fixes → new version**. A new version is created.
7. Press **Send to Manager**.
8. Click **Switch role** → **Try as Manager** → open the item → **Send to Approver**.
9. **Switch role** → **Try as Approver** → **Open approval decision** → **Approve**.

---

## Roles

| Role | Can author | Can review | Can approve |
|---|---|---|---|
| Creator | ✅ | — | — |
| Manager | — | ✅ | — |
| Approver | — | — | ✅ |

Roles are enforced **in the backend**, not only the UI. Managers and approvers
cannot create submissions, so the person who writes a draft is never the person
who approves it.

This is a demo role-selection flow, not production identity management: anyone
who can reach the demo can choose a role. Sessions expire after 12 hours by
default and are revoked when signing out. Guideline uploads are parsed in memory
and are not saved to object storage. Do not use the demo to protect confidential
or production content.

---

## Testing

```powershell
Set-Location backend
.venv\Scripts\python.exe -m pytest tests -v
```

The suite includes focused checks for evidence validation, minimal revision
spans, visual colour/contrast results, workflow transitions, duplicate actions,
invalid input, demo-session expiry/revocation, CORS allowlisting and
workspace-scoped retrieval. See [COMPLETED_FEATURES.md](./COMPLETED_FEATURES.md)
for an honest list of what works and what remains partial.

Build the frontend with:

```powershell
Set-Location frontend
npm ci
npm run build
```

The final submission and roadmap are in [SUBMISSION.md](./SUBMISSION.md).
Regenerate the product PDF after editing that file:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe ..\scripts\build_submission_pdf.py
```

---

## Deployment

The app is deployed:

- **Frontend:** [https://brand-shield-amber.vercel.app/](https://brand-shield-amber.vercel.app/)
- **Backend API:** [https://brandshield-api-eweqbqd8bpbwhbcn.centralindia-01.azurewebsites.net/](https://brandshield-api-eweqbqd8bpbwhbcn.centralindia-01.azurewebsites.net/)
- **Source repository:** [https://github.com/krishnabhatiadesigns/BrandShield](https://github.com/krishnabhatiadesigns/BrandShield)

For a separate deployment, set `VITE_API_URL` on the frontend to the backend
URL, and `CORS_ORIGINS` on the backend to the frontend's exact origin (for
example, `https://your-site.example`). Wildcard origins are rejected. Use
`/health` as the keep-warm ping.

The live frontend and backend `/health` endpoint were checked on 18 November
2026. A reachable URL does not replace testing the full workflow on the target
deployment after configuration changes.

---

## Disclosure

**Libraries**

- Backend: FastAPI, Pydantic, uvicorn, rank_bm25, httpx, PyMuPDF, python-docx, Pillow, numpy, psycopg
- Frontend: React, Vite, Tailwind CSS, React Router

**APIs**

- Groq (`openai/gpt-oss-120b`) for LLM analysis, called server-side only
- PostgreSQL is supported as a generic database option; local development
  defaults to SQLite.

**AI assistance**

This project was built with AI assistance (GitHub Copilot). All code was
reviewed, run and verified against a live server during development.

**Not used**

- OCR — deliberately skipped. Scanned PDFs are rejected with a clear message
  rather than silently returning nothing.
- Local embeddings — Groq has no embeddings endpoint; BM25 was sufficient.

---

## Licence

Demo project. All company data ("Northwind Foods") is fictional.
