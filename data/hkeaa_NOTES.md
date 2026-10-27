# Official HKEAA multiple-choice items

## What this file is

`hkeaa_mc_raw.json` holds **10 genuine HKDSE Geography Paper 1 Section A
multiple-choice items**, transcribed verbatim from HKEAA's own post-examination
briefing decks, with the **official correct answer** (the option HKEAA marks with
an asterisk) and HKEAA's own commentary on why candidates chose the distractors.

Every stem, every option and every answer letter in the JSON was read directly
off the source slide. Nothing was reconstructed, inferred or guessed.

Year coverage: **2022, 2024, 2025, 2026** (3 + 2 + 3 + 2). No 2023 item is
included — the 2023 deck's only Section A slide (Item 2) needs the Hong Kong map
extract, see the skipped list below.

## The honest headline: HKEAA does not publish full past papers for free

The authoritative source — the **Subject Examination Report and Question Papers
(with Marking Schemes)** — is a **paid publication**:

- Repository: <https://www.hkeaa.edu.hk/en/resources/publications/list_of_publications/hkdse_erqp_pub/>
- Per-year page (e.g. 2023): <https://www.hkeaa.edu.hk/en/resources/publications/list_of_publications/hkdse_erqp_pub/2023.html>

Each year page lists the paper, the PLU (product code) and the price — for
Geography, English version PLU **3795**, HK$85 for 2025 — and exposes only an
**order form** (`form_hkdse_2023_erqp.pdf`). There is no free PDF download of
the question paper or the marking scheme. The same applies to the HKCEE/HKALE
back catalogue.

HKEAA also states plainly that it **holds copyright** in these papers:

- Permission for reproduction: <https://www.hkeaa.edu.hk/en/resources/publications/qps/>
- School licence (paid, with usage tiers): <https://www.hkeaa.edu.hk/en/resources/publications/licence/>

The free alternatives that do exist are (a) the briefing decks below, (b) the
Assessment Frameworks, and (c) the **Samples of Candidates' Performance** —
which are candidate scripts, not question papers (see below).

## What the briefing decks actually contain

The `GEOG-PowerPoint-YYYY.pdf` decks are HKEAA's **examination briefing
slides**, published for teachers and centres. They are free. But their Section A
coverage is mostly **candidate performance statistics**, not papers:

- how many candidates answered correctly out of 20,
- which option **most** candidates picked (often a distractor),
- and, on the better slides, a **complete item**: the stem, all four options,
  the percentage who chose each, and an asterisk on the correct one.

HKEAA only reproduces a complete item where the distractor was *more* popular
than the key ("Four questions in which distractors were more popular than the
key have been selected for further discussion" — 2022 deck, p.16). That is why
the complete set is small: roughly 18 Section A slides across five decks, of
which only some carry the full item, and only a subset of those are usable
without a figure.

**They are not full papers.** Do not treat these decks as a substitute for the
question papers.

## Sources used

| Deck | URL | Items taken |
|---|---|---|
| 2022 | <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/GEOG-PowerPoint-2022.pdf> | 3 (pp. 17, 19, 20) |
| 2024 | <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/GEOG-PowerPoint-2024.pdf> | 2 (pp. 19, 21) |
| 2025 | <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/GEOG-PowerPoint-2025.pdf> | 3 (pp. 14, 15, 16) |
| 2026 | <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/GEOG-PowerPoint-2026.pdf> | 2 (pp. 12, 13) |

Also consulted and found **not** to contain usable items:

- 2021 make-up briefing deck: <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/PowerPoint-GEOG-2112-C.pdf>
  — Section A is covered only by statistics (p. 24); no complete item on any page.
- 2023 briefing deck: <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/GEOG-PowerPoint-2023.pdf>
  — one Section A slide (p. 22), Item 2, skipped (needs the map extract).
- Paper 1 sample format: <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/GEOG-Paper1SampleFormat-2019-E.pdf>
  — layout only, all questions blanked.
- Geography sample paper (Chinese only): <https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/geog/geog-SamplePaper-Paper1-2-c.pdf>
  — **40 Section A MC questions are present and readable, but no answer key is
  published alongside it**, so no official answer letters are available. Excluded
  on the "do not guess an answer" rule. Worth revisiting if HKEAA ever posts the key.
- `ppt1.pdf` (HKEAA curriculum-development deck) — no Section A items.

## The 10 items

| Year | Item | Elective | Subtopic | Answer | Deck | Page |
|---|---|---|---|---|---|---|
| 2022 | 11 | CP3 | CP3.1 | A | GEOG-PowerPoint-2022.pdf | 17 |
| 2022 | 16 | CP5 | CP5.3 | D | GEOG-PowerPoint-2022.pdf | 19 |
| 2022 | 17 | CP6 | CP6.2 | A | GEOG-PowerPoint-2022.pdf | 20 |
| 2024 | 12 | CP3 | CP3.1 | B | GEOG-PowerPoint-2024.pdf | 19 |
| 2024 | 20 | CP7 | CP7.3 | A | GEOG-PowerPoint-2024.pdf | 21 |
| 2025 | 5 | CP4 | CP4.4 | B | GEOG-PowerPoint-2025.pdf | 14 |
| 2025 | 19 | CP7 | CP7.3 | A | GEOG-PowerPoint-2025.pdf | 15 |
| 2025 | 20 | CP7 | CP7.3 | B | GEOG-PowerPoint-2025.pdf | 16 |
| 2026 | 14 | CP4 | CP4.4 | D | GEOG-PowerPoint-2026.pdf | 12 |
| 2026 | 16 | CP5 | CP5.6 | B | GEOG-PowerPoint-2026.pdf | 13 |

Per-elective: **CP3 = 2, CP4 = 2, CP5 = 2, CP6 = 1, CP7 = 3.** No CP1, CP2 or
EP1 item was recoverable — see the skipped list.

Each record also carries `option_percent` (the percentage of candidates who
chose each option, as published by HKEAA), `source_url` and `source_page`.

## Items found but skipped, and why

These are items HKEAA does publish a complete version of, but which cannot be
used as standalone drilling questions.

| Year | Item | Deck page | Why skipped |
|---|---|---|---|
| 2023 | 2 | GEOG-PowerPoint-2023.pdf p.22 | Requires the Hong Kong map extract (the item asks about the symbol at grid reference 513114). The four options are map symbols — car park, green minibus terminus, restricted access, LPG filling station — and are meaningless without the map. |
| 2025 | 3 | GEOG-PowerPoint-2025.pdf p.13 | Requires the map extract: the average gradient of a footpath between two grid references needs the contour heights and the measured distance. |
| 2024 | 6 | GEOG-PowerPoint-2024.pdf p.16 | Requires the map extract (grid square 0979, Wong Chuk Yeung). All three statements are about what the map shows. |
| 2024 | 9 | GEOG-PowerPoint-2024.pdf p.18 | Requires the coastal diagram (the spit, its growth direction and the wind arrow). |
| 2024 | 13 | GEOG-PowerPoint-2024.pdf p.20 | Requires the photograph of land use X (a container terminal). |
| 2022 | 13 | GEOG-PowerPoint-2022.pdf p.18 | Requires the three population-density graphs (stages 1–3). |

Skipping these follows the instruction that a question without its figure is
useless to a student. The decks are still a legitimate source if the site ever
wants to ship the cropped figure images alongside the questions — the crop
machinery in `scripts/crop_papers.py` already exists for that.

## Deliberately not used

- **Candidate script exemplars** (`*Sample-geog-Level*-E.pdf`,
  `*Sample-geog-Intro-E.pdf`, `2023-Sample-geog-Level5-E-9334.pdf`,
  `2024-Sample-geog-Level5-E-197S.pdf`, etc.). These are HKEAA's published
  **Samples of Candidates' Performance** — real exam scripts, some carrying
  candidate seat numbers and identifying marks. They are not question papers,
  and mining questions out of them is both the wrong source and a
  student-privacy problem. They were found, then deleted from disk without
  being used. Nothing from them appears in the JSON.
- **Oxford / 600MC question books** in the vault
  (`DSE Geography/MC Question Bank/`). Publisher material licensed for
  classroom use only; the teacher's own note says do not redistribute.
- **Predicted Grade Tests, Combo Quizzes and "Paper 2 Ans.pdf"** in the vault.
  Assessment material, excluded from the site entirely.
- **Third-party past-paper sites** (e.g. dse.best). Not an official HKEAA or EDB
  source, so the provenance of the question text and answer key cannot be
  guaranteed.
- **Any item whose stem or options I could not read with full confidence.**
  Where a slide's PDF text layer was ambiguous, the page was rendered to an
  image and transcribed visually; if it still could not be read cleanly, it was
  dropped rather than reconstructed.

## Consequence for the MC bank

The repository cannot serve full official past-paper MC questions without
purchase, so the MC bank is mostly AI-generated from the MakGeography notes,
with these official items as the genuine sample.

### Practical note for whoever runs the pipeline

`scripts/extract_hkeaa_mc.py` re-derives `hkeaa_mc_raw.json` from the decks by
reading PDF text geometry. Its parser was tested against the pages in this file
and **failed to parse 5 of the 10** (the three 2022 pages, the 2025 Item 5 and
2025 Item 20 pages), and it targets a different item set that includes the
figure-dependent items listed above. Running it will therefore **overwrite this
verified file with a worse one**. The JSON here is hand-verified against the
source slides; if the script is kept, its `KNOWN_ITEMS` map and parser need to
be brought into line with this file first, and the figure-dependent items
dropped.

`data/mc_bank.json` currently holds 6 official items from an earlier run,
including figure-dependent ones (2024 Q6, Q9, Q13) and one mis-tagged item
(2024 Q20 is tagged `CP2` but is a CP7 climate-change item). Re-running the bank
build after updating `hkeaa_mc_raw.json` will fix both.
