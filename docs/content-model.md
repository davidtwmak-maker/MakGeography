# The content model

Four sections, one body of source content: the teacher's Obsidian vault.

## Where each section gets its content

| Section | Source | Refreshed by |
|---|---|---|
| Ask (chatbot) | `data/kb.json` — vault notes, chunked and indexed | `scripts/build_kb.py` |
| Notes | `data/curriculum.json` + `data/kb.json` — official sub-questions with the vault note matched into each leaf | `scripts/build_curriculum.py` |
| MC Drilling | `data/mc_bank.json` — HKEAA past-paper questions + questions generated from the notes | `scripts/build_mc_bank.py` |
| News Corner | `data/news.json` — RSS/Atom feeds, tagged by elective | `scripts/collect_news.py` |

## The curriculum scaffold

`data/curriculum.json` follows the **official HKDSE Geography Curriculum and
Assessment Guide** (HKEAA, edb.gov.hk), which lists numbered guiding questions
for each elective. The current structure:

| Code | Elective | Sub-questions | Leaves |
|---|---|---|---|
| CP1 | Earth Structure | 4 | 16 |
| CP2 | Managing Coastal Environments | 2 | 11 |
| CP3 | Industrial Location | 6 | 6 |
| CP4 | Building a Sustainable City | 6 | 6 |
| CP5 | Combating Famine | 6 | 6 |
| CP6 | Disappearing Green Canopy | 5 | 14 |
| CP7 | Climate Change | 6 | 17 |
| EP1 | Dynamic Earth — the building of Hong Kong | 5 | 16 |

Each leaf carries `source_hints` — the vault note titles that hold that
content. The Notes page matches a leaf to its note and shows the real text
under the curriculum heading. A leaf with no matching note is shown honestly
as "no note yet" rather than hidden, so gaps are visible.

### 2027 changes

Three of the Section B fieldwork modules change for 2027:
Changing Industrial Location, Managing Coastal Environment, and — new —
**Building a Sustainable City**. Climate Change moves out of Section B.

## MC questions

197 questions across 93 sub-topics, every one of the 92 curriculum leaves
covered.

Two rules govern the bank:

1. **Nothing derived from a test.** No mocks, no predicted papers, no
   teacher-written question sets, no mark schemes.
2. **Nothing from a commercial book.** The Oxford and 600MC question banks in
   the vault are licensed for classroom use only and are excluded from the
   repository, images included.

What is in the bank:

- **13 official HKEAA questions** — the genuine exam wording, with the
  official answer, and a link to the HKEAA slide it was read from.
- **Generated questions** — written from the MakGeography notes, in DSE
  multiple-choice style. Each has four options, one answer, and an
  explanation that teaches the concept rather than just naming the answer.

The generator asks the model for questions against retrieved note chunks, so
every question is grounded in the notes the students are studying. When a
call times out on a long prompt, it retries with a tighter context, which
comes back reliably.

## Mistake tracking

Browser-local, keyed by sub-topic rather than elective:

- `makgeo_mc_stats` in `localStorage` holds attempts, correct count, and a
  per-sub-topic breakdown.
- **Drill my weak topics** pulls questions from the sub-topics the student is
  weakest in, putting the ones they already got wrong first.
- The mistake report shows a per-sub-topic bar, not just per-elective. A
  student weak on "Silicon Valley" does not need more iron-and-steel
  questions.

There is no server-side store, so no student is identifiable and nothing is
collected. If per-student histories are wanted later, that needs accounts and
a database, and is a deliberate decision rather than a default.

## Exclusion rules

**The rule:** a student may see material that teaches the syllabus. A student
may not see a test, a mock, a predicted paper, an answer key, a mark scheme,
or anything derived from them.

This is enforced in four places:

1. `scripts/build_kb.py` — path patterns and filename substrings
2. `scripts/build_kb.py` — section headings dropped from inside included notes
3. `scripts/verify.py` — the chunk TEXT is scanned, not just the path
4. `.github/workflows/ci.yml` — CI runs the verifier, so a leak fails the build

### The leak that a path check cannot catch

**A path check is not enough.** Assessment material does not always live in a
file called "answer key" — it lives *inside* an otherwise-shareable note, at
the end, under a heading like "Teacher key and rationale".

Two real examples from the vault:

- `CP2/CP2 MC/Coastal MC.md` — student-facing questions followed by
  `# Teacher key and rationale`: the key to all eight items, the distractor
  reasoning, and the **register of stems already used**.
- `F3 Geography/F3 Kahoot drill ...` — a full teacher answer key and
  distractor rationale table, in a file with no markdown headings at all, so
  a heading-based drop could never reach it.

Both were reachable by any signed-in student through the Notes page and
through the chatbot's citations.

The rules that came out of it:

- **Drop the section, keep the note.** A note with a teacher key at the end
  is still a good note for the first part. Excluding the whole file throws
  away the teaching content.
- **Match on the heading, drop to the next heading.** The drop removes
  everything from the matched heading to the next heading of the same or
  higher level.
- **If a file has no headings, a heading rule cannot save it.** Exclude the
  file outright.
- **Verify on the text, not the path.** `scripts/verify.py` scans every
  chunk's text for the teacher-only markers, so this cannot regress
  silently.

### Commercial MC books

The Oxford and 600MC books in the vault are **publisher material licensed for
classroom use only** ("do not redistribute" per the teacher's own note). They
are excluded from the repository entirely, images included.

### What HKEAA actually publishes for free

This matters, because the obvious assumption — that HKEAA's past papers are
free online — is **wrong**, and the difference changes what the site can
offer.

- The **Subject Examination Report and Question Papers (with Marking
  Schemes)** is a **paid publication**. Each year page lists a price and
  exposes only an order form. There is no free PDF of the paper or the key.
  HKEAA also states that it holds copyright in them.
- The **examination briefing decks** are **free**, but their Section A
  coverage is mostly candidate performance statistics. A handful of slides do
  carry a complete item — stem, four options, the correct option marked with
  an asterisk, and the percentage who chose each option. That is where the 13
  official questions come from.
- The **Samples of Candidates' Performance** are candidate scripts, some
  carrying seat numbers. They were found, then deleted from disk without
  being read. Nothing from them is in the repository.

So the honest position is: the official papers cannot be served without
purchase, and the rest of the bank is generated from the MakGeography notes.
`data/hkeaa_NOTES.md` records the full provenance, including which items
were found and why three of them were excluded.

**The asterisk is the key, not the percentage.** On these slides the option
with the *highest* percentage is usually the most popular **wrong** answer.
On 2022 Q11 the key had 31% against a popular wrong answer at 32%; on Q16
the key had 28% against 52%; on Q17 the key had 29% against 48%. Reading the
percentage column instead of the asterisk would have got all three wrong.

**A question needing its figure.** An item was skipped only if the figure it
depends on is NOT printed on its own slide. 2022 Q13, 2024 Q9 and 2024 Q13 do
print their figure, so they are included and the site shows the slide. The
three that genuinely need the Hong Kong map extract (2023 Q2, 2024 Q6, 2025
Q3) stay out.

**Verification.** Each transcription was checked by up to three independent
methods — a full-slide vision read, zoomed region crops, and macOS Vision
OCR for a literal character-level read. Where two passes disagreed, the OCR
settled it. The deck PDFs are HKEAA's files and are gitignored; only the
rendered question crops are committed, served behind the password gate with
HKEAA credited on each.

## Plain-language rule

The notes are for students who have not met the industry vocabulary. The
figures and notes use plain terms:

| Instead of | Write |
|---|---|
| GCC (global capability centre) | a multinational's own in-house delivery centre |
| IT-BPM | IT and business-process services |
| CAGR | growing N% a year |
| FDI | foreign direct investment |
| SMT / SPI / AOI / ICT / FCT | Solder paste print / Paste inspection / Optical inspection / X-ray & electrical test |

CP3 syllabus vocabulary — *TNC*, *deindustrialisation*, *footloose* — is kept,
because that is the course's own language and what the exam rewards.

## Retrieval

`app/kb.py` implements BM25 (pure Python, no sklearn) over ~1,400 chunks.

Three things make it work for this corpus:

- **Heading and title weighting.** A chunk headed "Silicon Valley" outranks one
  that mentions it once. Title tokens count double, heading tokens triple.
- **Geography synonyms.** "tsunami" also pulls "seismic sea wave";
  "footloose" pulls "location factor"; "famine" pulls "food insecurity".
- **Elective filtering.** Choosing CP3 boosts CP3 chunks and damps the rest,
  so a broad question still stays on the elected topic.

A keyword index beats embeddings here: the corpus is small, and the vocabulary
is a closed set of syllabus terms that embedding models tend to blur together.
