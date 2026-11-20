# ROUND3_IMPROVEMENTS

Three meaningful, non-cosmetic improvements.

---

## 1. Evidence-backed verification hardening

### The problem

An LLM will happily invent a citation. If a finding says "this contradicts the
brand guide, passage 47" and passage 47 does not exist — or belongs to another
workspace — the finding is worse than useless: it is confidently wrong.

### What was built

`app/validation.py` treats every LLM finding as a **proposal**, not a result. It
must survive five checks before reaching the database:

| Check | Failure behaviour |
|---|---|
| Affected text exists in the draft | Discard the finding |
| Cited passage exists, is approved, is in force, same workspace | Downgrade to `needs_verification` |
| `supported`/`contradicted` requires a valid citation | Downgrade to `needs_verification` |
| Suggestion introduces unapproved numbers | Remove the suggestion |
| Category/severity are known values | Clamp |

The retrieval layer reinforces this: the SQL filter on `workspace_id` and
`status = 'approved'` runs **before** BM25 ranking, so a passage from another
workspace can never be retrieved even if it would score highest.

### Why it matters

The distinction between `contradicted` and `needs_verification` is the whole
point of the product. A claim is only called contradicted when an approved source
actually contradicts it. Everything else is flagged for a human.

**Verified:** the email sample's "USDA Organic" claim is marked `contradicted`
because the fact sheet explicitly says the bars are *not* USDA Organic. The ad's
"100% natural ingredients" is marked `needs_verification` because no approved
source addresses it. Those are different outcomes for a reason.

---

## 2. Context-preserving corrections

### The problem

A rewrite that changes more than the problem is not a fix — it is the tool
overriding the author. Early versions produced duplicated text because
suggestions were full sentences while spans were single words.

### What was built

**An explicit contract:** `suggestion` replaces exactly `[span_start, span_end)`.
Nothing else in the draft moves.

**Enforced at apply time** in `revise_content`:

- Spans are applied **back to front** so earlier offsets stay valid.
- **Overlapping spans are skipped** — applying two edits to the same characters
  would corrupt the draft.
- The stored span is **re-verified against the current text** before applying. If
  the draft drifted, the edit is skipped rather than corrupting the document.

**Grammar-aware replacements:** a prohibited term whose replacement starts with
"a"/"an" absorbs a preceding article, so "We're the #1" becomes "We're a leading"
rather than "We're the a leading". A product-name fix absorbs a trailing "bars"
so "Northwind Harvest Oat Crunch bars" becomes "Northwind Harvest Oat Bars", not
"…Oat Bars bars".

**Intent checks in validation:** a suggestion that introduces numbers not present
in the affected text and not in the approved facts is removed. A suggestion longer
than 6× the affected text is removed as an over-rewrite.

### Why it matters

The creator's intent survives. Accepting every fix on the LinkedIn sample produces
a draft that still reads like the original author wrote it:

> We're thrilled to announce that Northwind Harvest Oat Bars are now available
> across India! 🎉
>
> Made with oats, almonds, honey and sea salt, our bars are the **affordable**
> wholesome snack you'll find. Northwind Harvest Oat Bars deliver **6g** of
> protein per bar — perfect for busy mornings.
>
> We're **a leading** oat bar brand in India, **designed** to keep you full all
> day. Grab yours today!

---

## 3. Visual brand compliance

### The problem

"Does this look on-brand?" is usually answered by opinion. Two things can be
measured objectively: whether a colour is close to the approved palette, and
whether text is readable against its background.

### What was built

`app/routers/visual.py` implements real colour science, not heuristics:

**Palette similarity — CIE76 ΔE**

sRGB → linear RGB → XYZ (D65) → CIE Lab, then Euclidean distance in Lab space.
ΔE < 10 is treated as on-brand. Lab is used rather than RGB distance because RGB
distance does not match human perception — two colours can be far apart in RGB
and look identical.

**Contrast — WCAG 2.1**

Relative luminance with the correct sRGB gamma curve, then
`(L_lighter + 0.05) / (L_darker + 0.05)`. Body text below 4.5:1 is flagged;
below 3:1 is escalated to high severity.

### Why it matters

Both produce numbers a designer can act on:

> `#FF0000` is not in the approved palette. The closest approved colour is
> Northwind Green (`#1F5C3A`), a CIE76 difference of 61.4.

> `#E8A33D` on `#F5EFE3` has a contrast ratio of 1.94:1, below the 4.5:1
> required by the visual identity standards.

### Honest limitation

The check accepts hex colours, not image files. Pixel sampling from an arbitrary
image needs region selection to be meaningful, and OCR was deliberately skipped.
The maths is real; the input path is simpler than planned.

---

## Round 3 verification

The 18 November 2026 Round 3 checkpoint added regression coverage for citation
and suggestion validation, context-preserving revisions (including overlap and
stale-span handling), visual checks, retrieval isolation, and the complete
creator → manager → approver journey. The suite has since grown to 46 tests,
including Supabase token, membership, invitation and deactivation coverage.
The frontend TypeScript check and production build also pass.
