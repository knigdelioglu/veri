# Iteration 2 — 3000 Record Production Plan

## Goal

Expand the canonical dataset from **1500 → 3000 verified records** and from **72 → 144 question families** while preserving rubric-first scoring, evidence-grounded review decisions, split/leakage isolation, and the target modality/grade/quality distributions.

## Batch shape

Iteration 2 adds 1500 records in 15 waves of 100 records.

- **I2-01 … I2-12:** 5 question families × 20 answers = 100 records per wave.
- **I2-13 … I2-15:** 4 question families × 25 answers = 100 records per wave; each family uses two exact tasks with 12/13 answers.
- Total new families: `12×5 + 3×4 = 72`.
- Final family count: `72 + 72 = 144`.

## Modality schedule

The new 1500 records must contribute exactly **750 written / 375 speaking / 375 listening**.

Materialized first-wave schedule:

- I2-01: `60 written / 20 speaking / 20 listening`
- I2-02: `40 written / 20 speaking / 40 listening`
- I2-03: `40 written / 40 speaking / 20 listening`
- I2-04: `60 written / 20 speaking / 20 listening`
- I2-05: `60 written / 20 speaking / 20 listening`

After I2-05 the canonical state is `1010 written / 495 speaking / 495 listening` at 2000 records. Exact 3000-record closure remains:

- I2-06 … I2-08: `60 written / 20 speaking / 20 listening`
- I2-09 … I2-10: `40 written / 40 speaking / 20 listening`
- I2-11 … I2-12: `40 written / 20 speaking / 40 listening`
- I2-13 … I2-15: `50 written / 25 speaking / 25 listening`

Across I2-01 … I2-12 this yields exactly `600/300/300` Iteration-2 records; the final three waves add `150/75/75`. Iteration 2 therefore closes exactly at **750/375/375 new records** and **1500/750/750 cumulative records**.

## Grade schedule

For I2-01 … I2-12, one grade receives two 20-answer families while the other grades receive one family each. The duplicated grade rotates:

`9, 10, 11, 12, 9, 10, 11, 12, 9, 10, 11, 12`.

Thus each grade receives 300 records in the first 12 waves. I2-13 … I2-15 contain one 25-answer family per grade, adding 75 more. Final Iteration 2 addition is exactly **375 per grade**, yielding **750 cumulative records per grade** at 3000.

## Response-quality profile

Each 100-record wave targets:

- full_correct: 20
- high_partial: 20
- mid_partial: 20
- low_partial: 15
- incorrect: 10
- blank_irrelevant: 5
- borderline: 10

Gold scores are never altered merely to hit these counts. If independent rubric review finds a mismatch, rewrite/regenerate answer evidence and rescore by rubric; retain any genuine resulting drift and compensate only through later evidence generation.

## Special-case targets

Per 100-record wave, a practical center target is:

- hard-case: ~18
- adversarial: 4
- genuine needs_review: 8
- second-pass AI review: 25

All borderline and needs_review records receive at least two review passes. `needs_review=true` is reserved for source/evidence uncertainty that can materially alter the score or interpretation. OCR/STT uncertainty remains separate from student answer text and, from I2-04 onward, the recorded uncertainty span must be grounded directly in the student response text.

## Invariants

- Rubric-first scoring; no quota-driven gold manipulation.
- `borderline != needs_review`.
- Synthetic records are `ai_verified`, never teacher-verified.
- Speaking synthetic records are transcript-only; no invented delivery/fluency evidence.
- Test remains sealed from generation/model selection.
- No connected family/task leakage across splits.
- Canonical record files remain source of truth.
- Every wave must pass production regressions, materialization, `veri check`, leakage, cumulative assertions, quota, idempotency, and a final clean CI run before merge.

## Current checkpoint after I2-05

- **2000/3000** canonical records
- **97/144** question families
- **194** exact tasks
- modality: `1010 written / 495 speaking / 495 listening`
- grades: `g9=515 / g10=495 / g11=495 / g12=495`
- remaining: **1000 records / 47 families**

## I2-06 target

- +100 records / +5 families / +10 exact tasks
- `60 written / 20 speaking / 20 listening`
- grade 10: 40; grades 9/11/12: 20 each
- cumulative after merge: **2100/3000 records, 102/144 families, 204 exact tasks**
- cumulative modality: `1070 written / 515 speaking / 515 listening`
- cumulative grades: **535 each**
