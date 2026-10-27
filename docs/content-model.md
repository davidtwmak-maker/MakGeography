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

## Exclusion rules

**The rule:** a student may see material that teaches the syllabus. A student
may not see a test, a mock, a predicted paper, an answer key, a mark scheme,
or anything derived from them.

This is enforced in three places:

1. `scripts/build_kb.py` — path patterns and filename substrings
2. `scripts/build_kb.py` — section headings dropped from inside included notes
3. `.github/workflows/ci.yml` — a CI check that fails the build if any
   assessment path appears in `kb.json`

### Commercial MC books

The Oxford and 600MC books in the vault are **publisher material licensed for
classroom use only** ("do not redistribute" per the teacher's own note). They
are excluded from the repository entirely, images included.

The MC section instead uses:

- **HKEAA past papers** — published for public examination, freely reusable
- **Generated questions** — written from the MakGeography notes, in DSE
  multiple-choice style, with an explanation that teaches the concept

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
