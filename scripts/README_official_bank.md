# The official HKEAA question bank

The MC Drilling tab carries the real HKDSE and HKCEE Geography questions,
fetched from the OQB (網上試題學習平台) at <https://oqb.edcity.hk>. There are
765 official questions covering the papers from 2005 to 2025.

Each question is stored the way it appeared on the paper:

- a **stem image** — the question, and often a photograph or diagram
- four **option images** — one per option
- the paper's **map extract**, for the map-reading section
- the **answer key**, straight from HKEAA

The OCR text is kept alongside the images so the questions can be searched
and filtered by topic. The images are the authority: the OCR is only ever
a convenience layer, and it is wrong in a few places (a table flattened
into a run of words, for instance). Where that happens the option is shown
as its image alone.

## Layout

    data/hkeaa_oqb/
      geog/<row-id>/            stem and option images (.webp)
      geog/_attachments/_files/ the map extracts, one per paper year
      hkeaa_mc_manifest.json    one row per question: source, topic, answer
      hkeaa_mc_manifest.csv     the same, as a spreadsheet
      attachment_map.json       which question needs which map extract
      ocr/geog.json             the OCR text, keyed by the OQB row id
      _raw/                     the raw API records — NOT committed

`_raw/` is excluded by `.gitignore` because the OQB records carry Azure
signed URLs and per-row access tokens.

## The pipeline

Run from the repository root, in this order:

    python scripts/oqb_api.py            # the OQB API client (search, blob fetch)
    python scripts/oqb_download.py       # fetch the records, images and maps
    python scripts/oqb_dedupe.py         # collapse the duplicated map extracts
    python scripts/oqb_reattach.py       # re-fetch the maps with unique names
    python scripts/oqb_attach_index.py   # map each question to its map extract
    python scripts/oqb_ocr.py            # OCR the images into searchable text
    python scripts/oqb_build_bank.py     # turn the records into question records
    python scripts/oqb_merge_bank.py     # merge them into data/mc_bank.json
    python scripts/oqb_webp.py           # convert the images to WebP
    python scripts/oqb_graphic_options.py  # flag the table/diagram options

Authentication is through HK Education City CAS. The password is not in
the repository: put it in the local credential store and `oqb_api.py` will
pick up the session token from `~/.hermes/cache/scratch/oqb_token.txt`.

## Two things that will bite you

**The answer key is zero-based.** OQB stores `"[0]"` for the *first*
option, not the second. This was verified against the eleven hand-checked
questions that were already in the bank (2022 Q11/Q13/Q16/Q17, 2024
Q9/Q12/Q13/Q20, 2025 Q5/Q19/Q20) — every one matched with zero-based
indexing.

**The array parameters are indexed, not bracketed.** The OQB API expects
`criteria[subject_code][0]=geog`, not `criteria[subject_code][]=geog`. The
latter is silently ignored and the server returns questions from the wrong
subject.

## Checks

    python scripts/test_official_bank.py   # 13 checks on the imported bank
    python scripts/verify.py                # the whole site

`test_official_bank.py` checks that every official question has an answer
in A–D, that all four of its images exist on disk, that no media path can
escape the data directory, that the answer key is spread across all four
options (a copy/paste slip would collapse it to one letter), and that the
hand-checked questions kept their explanations.

## Serving the media

`app/main.py` serves the images from `/oqb-images/<path>` and the map
extracts from `/oqb-attachments/<path>`. Both resolve the path and then
confirm it is still inside `data/hkeaa_oqb/`, so a crafted path cannot
reach outside it.
