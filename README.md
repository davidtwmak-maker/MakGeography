# MakGeography

**HKDSE Geography study site for Form 6 students.**

A public, password-protected website with four sections:

| Section | What it does |
|---|---|
| **Ask** | A chatbot that answers from the MakGeography notes and shows which note each answer came from |
| **Notes** | CP1–CP7 and EP1, scaffolded by the official HKDSE curriculum sub-questions |
| **MC Drilling** | Practice multiple choice by elective, with a mistake report that shows which topics to drill next |
| **News Corner** | Current geography news, auto-tagged by elective, refreshed on a schedule |

---

## Quick start

```bash
git clone https://github.com/davidtwmak-maker/MakGeography.git
cd MakGeography

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# The knowledge base is built from the Obsidian vault (see below).
# A prebuilt copy ships in data/kb.json so you can run immediately.

export MAKGEO_PASSWORD='choose-a-password'
export MINIMAX_API_KEY='your-minimax-key'
export MINIMAX_BASE_URL='https://api.minimax.io/v1'

uvicorn app.main:app --host 127.0.0.1 --port 8781
```

Open <http://127.0.0.1:8781> and sign in with your password.

---

## Configuration

Everything is read from the environment. **Never commit a real key.**

| Variable | Required | Purpose |
|---|---|---|
| `MAKGEO_PASSWORD` | yes | The shared site password. Also read from `~/.hermes/.env`. **There is no default** — the app refuses to start without one, because a password committed to a public repository is not a password. |
| `MINIMAX_API_KEY` | yes | Key for the LLM that answers questions. |
| `MINIMAX_BASE_URL` | no | Defaults to `https://api.minimax.io/v1`. |
| `MAKGEO_VAULT` | no | Path to the Obsidian vault. Defaults to the path in `scripts/build_kb.py`. |

### Model choice

`app/llm.py` uses a fallback chain:

```
MiniMax-M2.5-highspeed  →  minimax-M3  →  MiniMax-M2.5
```

The fast model leads. `minimax-M3` reasons at length and on a large context
it can spend the entire time budget without producing an answer — measured at
a 354 s timeout against 12.8 s for the fast model on the same payload. The
stronger model stays as a fallback for short questions.

---

## Building the knowledge base

The notes come from the teacher's Obsidian vault. The builder is a filter, not
a copy: **tests, mocks, predicted papers, answer keys and mark schemes are
excluded**, because that material must never be exposed to students or
published publicly.

```bash
python scripts/build_kb.py                    # vault → data/kb.json
python scripts/build_curriculum.py            # → data/curriculum.json
python scripts/build_mc_bank.py --per-subtopic 2   # → data/mc_bank.json
python scripts/collect_news.py                # → data/news.json
```

### What is excluded, and why

`scripts/build_kb.py` has three exclusion layers:

1. **Path patterns** — `Past Paper (DBQ)`, `Past Paper (SE)`, `Predicted Grade
   Test`, `First Term Test`, `Combo Quiz`, `DBQ (practice)`, `Data Question
   Set`, `MC Question Bank`, `MC Quiz`.
2. **Filename substrings** — `ans`, `answer`, `mark scheme`, `predicted grade
   test`, `mock`, `candidate marks`.
3. **Section headings inside included files** — a `## Mark Scheme` section is
   dropped even if the rest of the note is fine.

The commercial MC books (Oxford, 600MC) are **publisher material licensed for
classroom use only** and are deliberately not redistributed here. The MC
section uses HKEAA past papers (published for public examination) and
questions generated from the notes.

---

## Architecture

```
app/
  main.py     FastAPI app: password gate, API routes, session handling
  kb.py       BM25 retrieval over the note chunks (pure Python, no sklearn)
  llm.py      MiniMax client: prompt construction, reasoning-strip, model fallback
templates/    Jinja2 templates (login, main UI)
static/       CSS + front-end JavaScript
scripts/      Builders for kb.json, curriculum.json, mc_bank.json, news.json
data/         Generated artefacts (committed so the site runs without the vault)
docs/         Notes on the content model and the exclusion rules
```

### Retrieval

`app/kb.py` implements BM25 with:

- a **heading and title weight** — a chunk titled "Silicon Valley" ranks higher
  for "silicon valley" than one that mentions it once in passing;
- **geography synonyms** — "tsunami" also retrieves "seismic sea wave",
  "footloose" retrieves "location factor";
- an **elective filter** that boosts the selected topic and damps others.

No vector database is needed at this corpus size (~1,400 chunks), and a
keyword index handles the geography vocabulary better than generic embeddings.

### Grounding

The chatbot only sees retrieved chunks, and is instructed to say so when the
notes do not cover a question. It cites the note it used:

> Silicon Valley is an example of a **footloose industry** because the IT
> industry has few fixed locational requirements … (3 Silicon Valley — 3.1
> Location Factors; 1.1 Industrial Location Factors — Other factors)

---

## Running as a service

`scripts/install_launchd.sh` installs a `launchd` job that keeps the app
running and restarts it if it crashes.

```bash
./scripts/install_launchd.sh
```

To put it on the public internet, run a tunnel in front of it. `cloudflared`
is the simplest option and needs no account for a quick tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:8781
```

**The site is password-protected, but a tunnel URL is guessable and the
password is the only thing standing between the internet and the notes.**
Use a strong password and treat the URL as secret. For a permanent deployment,
use a named Cloudflare tunnel with access policies rather than a quick tunnel.

---

## Deploying

The repo is public. The **code** is public; the **vault notes are not** — they
are not committed. `data/kb.json` is a derived artefact of the teacher's own
notes and is committed so the site can run standalone; if that changes,
remove it from git and add it to `.gitignore`.

---

## Licence

Code: MIT — see `LICENSE`.

Notes and question content: © David Mak, all rights reserved. They are included
for classroom use by MakGeography students and may not be redistributed.
