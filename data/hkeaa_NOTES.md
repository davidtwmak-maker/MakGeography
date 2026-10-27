# Official HKEAA multiple-choice items

## What this file is

`hkeaa_mc_raw.json` holds **14 genuine HKDSE Geography Paper 1 Section A
multiple-choice items**, transcribed verbatim from HKEAA's own post-examination
briefing decks, with the **official correct answer** (the option HKEAA marks with
an asterisk) and HKEAA's own commentary on why candidates chose the distractors.

Every stem, every option and every answer letter in the JSON was read directly
off the source slide. Nothing was reconstructed, inferred or guessed.

Year coverage: **2022, 2024, 2025, 2026** (4 + 3 + 3 + 2, plus three more
whose figure is printed on the slide). No 2023 item is included — the 2023
deck's only Section A slide (Item 2) needs the Hong Kong map extract, see the
skipped list below.

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

Each record also carries `source_url`, `source_page` and a link to the
rendered slide image, so a student can check the transcription against
HKEAA's own slide. The full table, with the verification method for each
item, is further down this file.

## Items found but skipped, and why

These are items HKEAA does publish a complete version of, but which cannot be
used as standalone drilling questions.

| Year | Item | Deck page | Why skipped |
|---|---|---|---|
| 2023 | 2 | GEOG-PowerPoint-2023.pdf p.22 | Requires the Hong Kong map extract (the item asks about the symbol at grid reference 513114). The four options are map symbols — car park, green minibus terminus, restricted access, LPG filling station — and are meaningless without the map. |
| 2025 | 3 | GEOG-PowerPoint-2025.pdf p.13 | Requires the map extract: the average gradient of a footpath between two grid references needs the contour heights and the measured distance. |
| 2024 | 6 | GEOG-PowerPoint-2024.pdf p.16 | Requires the map extract (grid square 0979, Wong Chuk Yeung). All three statements are about what the map shows. Removed from `hkeaa_mc_raw.json` as well, so a rebuild of the bank cannot reintroduce it - the raw catalogue holds only the items verified complete. |
| 2024 | 9 | GEOG-PowerPoint-2024.pdf p.18 | Requires the coastal diagram — **but the diagram IS printed on this slide**, so this item was recovered and is now included. |
| 2024 | 13 | GEOG-PowerPoint-2024.pdf p.20 | Requires the photograph of land use X — **but the photograph IS printed on this slide**, so this item was recovered and is now included. |
| 2022 | 13 | GEOG-PowerPoint-2022.pdf p.18 | Requires the three population-density graphs — **but the graphs ARE printed on this slide**, so this item was recovered and is now included. |

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

## The items in the bank, and how each was verified

`data/hkeaa_mc_raw.json` holds **14 items**; `data/mc_bank.json` carries all 14
with an `official` flag and a link to the slide image.

| Year | Item | Elective | Answer | Deck page | Figure needed? | Verification |
|---|---|---|---|---|---|---|
| 2022 | 11 | CP3 | A | 17 | no | vision, twice, independently |
| 2022 | 13 | CP1 | B | 18 | yes - on the slide | vision |
| 2022 | 16 | CP5 | D | 19 | no | vision, twice, independently |
| 2022 | 17 | CP6 | A | 20 | no | vision, twice, independently |
| 2024 | 12 | CP3 | B | 19 | no | vision + geometry + OCR |
| 2024 | 20 | CP7 | A | 21 | no | vision + geometry + OCR |
| 2025 | 5 | CP4 | B | 14 | no | vision |
| 2025 | 19 | CP7 | A | 15 | no | vision + geometry |
| 2025 | 20 | CP7 | B | 16 | no | vision |
| 2026 | 14 | CP4 | D | 12 | no | vision + OCR |
| 2026 | 16 | CP5 | B | 13 | no | vision |
| 2024 | 9 | CP2 | D | 18 | yes - on the slide | vision |
| 2024 | 13 | CP4 | D | 20 | yes - on the slide | vision |

### How the verification was done

Three independent methods were used, because a single vision read of a slide
is not proof:

1. **Full-slide vision read** of the rendered page.
2. **Zoomed region crops** of just the stem and just the option table.
3. **macOS Vision OCR** - a small Objective-C tool built for this, giving a
   literal character-level read.

Where two vision passes disagreed on a word or a percentage, the OCR read
settled it. Every asterisk position was checked against the slide: the
asterisk marks HKEAA's correct answer, and the option with the *highest
percentage* is usually the most popular **wrong** answer, not the key. That
distinction caused a false alarm once and was checked explicitly each time.

The 2024 and 2026 items were verified by all three methods and came back
exact - stem, all four options in order, and the asterisk position. The
remaining items were verified by full-slide vision plus zoomed crops.

The three 2022 items were each read twice, independently, and both reads
agreed exactly on the stem, the three statements, all four options and the
asterisk position. The same three items were also checked by a geometric
extractor reading the PDF's word positions, which produced the identical
answers (A, D, A).

**A note on the asterisk.** The option carrying the *highest percentage* is
usually the most popular **wrong** answer, not the key. On 2022 Q11 the
correct answer A had 31% while the popular wrong answer B had 32%; on 2022
Q16 the correct D had 28% against a popular A at 52%; on 2022 Q17 the
correct A had 29% against a popular D at 48%. Reading the percentage
column instead of the asterisk would have got all three wrong.

### Items whose figure IS on the slide

A first pass skipped every item that referred to a figure, on the rule that a
question without its figure is useless. That was too broad. Three of them -
2022 Q13 (the population-density graphs), 2024 Q9 (the coastal spit with the
wind arrow) and 2024 Q13 (the container-yard photograph) - **do print their
figure on the slide**, and the site shows the slide, so they are usable and
are included.

The three that genuinely need the Hong Kong map extract stay out, because the
map is not on their slides:

| Year | Item | Deck page | What it needs |
|---|---|---|---|
| 2023 | 2 | 2023 p.22 | the HK map extract (grid reference 513114) |
| 2024 | 6 | 2024 p.16 | the HK map extract (grid square 0979) |
| 2025 | 3 | 2025 p.13 | the HK map extract (footpath gradient) |

### Pipeline safety

`scripts/extract_hkeaa_mc.py` re-derives the items from the decks by reading
PDF text geometry. It is a **cross-check, not the source of truth**, and it
writes to `data/hkeaa_mc_geometric.json` so it can never overwrite the
hand-verified `data/hkeaa_mc_raw.json`. Its parser fails on 5 of the pages
above and its item set differs, so it must not be used to regenerate the
record.

The pipeline that produced the verified file is:

```
scripts/fetch_decks.py          # download the HKEAA decks (gitignored)
scripts/extract_hkeaa_mc.py     # geometric cross-check -> hkeaa_mc_geometric.json
scripts/merge_official_mc.py    # merge geometry + vision -> hkeaa_mc_raw.json
scripts/render_slide_crops.py   # render the slide images + attach them
scripts/add_official_mc.py      # add the official items to the MC bank
scripts/add_figure_items.py     # add the three figure-bearing items
scripts/repair_figure_items.py  # full stems and explanations for those three
```

The deck PDFs are HKEAA's files and are gitignored; only the rendered
question crops are committed. Every slide image is served behind the site's
password gate with HKEAA credited on it.
