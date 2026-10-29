# MakGeography

**HKDSE Geography study site for Form 6 students.**

A public website with five sections:

| Section | What it does | State |
|---|---|---|
| **Ask** | A chatbot that answers from the MakGeography notes and shows which note each answer came from | working |
| **Notes** | CP1–CP7 and EP1, scaffolded by the official HKDSE curriculum sub-questions | working — 126 leaves, all sourced |
| **MC Drilling** | Practice multiple choice by elective, with a mistake report that shows which topics to drill next | working — 1,018 questions (767 official HKEAA exam questions, 2005–2025) |
| **Essay Generator** | Builds a practice essay from the notes: a question stem, a mark scheme and an exemplar answer | working — CP1–CP7 and EP1 only |
| **News Corner** | Current geography news, auto-tagged by elective, refreshed on a schedule | working — 29/30 feeds |

---

## Quick start

```bash
git clone https://github.com/davidtwmak-maker/MakGeography.git
cd MakGeography

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# The knowledge base is built from the Obsidian vault (see below).
# A prebuilt copy ships in data/kb.json so you can run immediately.

# Optional. With no MAKGEO_PASSWORD the site is open to everyone.
# export MAKGEO_PASSWORD='choose-a-password'
export MINIMAX_API_KEY='your-minimax-key'
export MINIMAX_BASE_URL='https://api.minimax.io/v1'

uvicorn app.main:app --host 127.0.0.1 --port 8781
```

Open <http://127.0.0.1:8781>. If you set a password, you will be asked for it;
if not, the site opens straight into the study tools.

---

## Configuration

Everything is read from the environment. **Never commit a real key.**

| Variable | Required | Purpose |
|---|---|---|
| `MAKGEO_TEACHER_KEY` | no | The teacher's own sign-in. Sign in as `teacher` with this. It is not in the student roster, so it cannot be guessed from it. |
| `MAKGEO_ROSTER_PATH` | no | Path of a `roster.json` on the server. The roster holds the students' names, so it is not committed. |
| `MAKGEO_ROSTER_JSON` | no | The roster inline, for a server where setting a file is awkward. `MAKGEO_ROSTER_PATH` is preferred — the roster is large. |
| `MAKGEO_ACTIVITY_LOG` | no | Where the activity log is written. Point this at a persistent disk on a hosted service. |
| `MAKGEO_PASSWORD` | no | A shared site password — the fallback gate, used when there is no roster. Also read from `~/.hermes/.env`. With none set and no roster, the site is open to everyone. |
| `MINIMAX_API_KEY` | yes | Key for the LLM that answers questions. |
| `MINIMAX_BASE_URL` | no | Defaults to `https://api.minimax.io/v1`. |
| `MAKGEO_VAULT` | no | Path to the Obsidian vault. Only used to rebuild the knowledge base. |

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
  main.py       FastAPI app: the sign-in gate, API routes, session handling
  roster.py     The student roster: SID sign-in, password hashing, activity log
  kb.py         BM25 retrieval over the note chunks (pure Python, no sklearn)
  curriculum.py Matches a curriculum sub-topic to the notes that cover it
  essay.py      The Essay Generator: source collection and prompt building
  llm.py        MiniMax client: prompt construction, reasoning-strip, model fallback
templates/    Jinja2 templates (login, main UI)
static/       CSS + front-end JavaScript
scripts/      Builders for kb.json, curriculum.json, mc_bank.json, news.json, roster.json
data/         Generated artefacts (committed so the site runs without the vault)
docs/         Notes on the content model and the exclusion rules
Dockerfile    The container image for a hosted deployment
render.yaml   A Render blueprint for the same
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

### The Essay Generator

`app/essay.py` turns a chosen elective and sub-topic into a practice essay:
a question stem, a mark scheme and an exemplar answer, in the real HKDSE
short-essay format (two paired-command parts, bands of 6 / 3–5 / 1–2 for a
12-mark essay).

It writes from the same notes the Notes section shows, reached through the
same curriculum scaffolding, so a student can check the essay against the
material they studied. The notes it used are listed under the essay.

**The scope is CP1–CP7 and EP1.** F2 and F3 are a different course with a
different syllabus, so the generator refuses them and never draws on their
notes — a practice essay that mixed the two would teach the wrong content.
`scripts/verify.py` checks this on every build: that F2 and F3 are refused,
that no F2/F3 note reaches the essay context, and that every one of the 126
sub-topics has enough material to carry an essay on its own.

---

## Signing in

Students sign in with their **own Student ID** and a password, so the site
can say who used it. The teacher signs in as `teacher` with
`MAKGEO_TEACHER_KEY`.

The roster is built from the school's own class list, so the names and SIDs
are the school's rather than retyped:

```bash
python scripts/build_roster.py                    # from the class list workbook
python scripts/build_roster.py --from-csv r.csv   # or from a CSV
python scripts/set_student_password.py --all --password 'term-start'
python scripts/set_student_password.py --sid 20233004 --print   # one random password
```

Passwords are PBKDF2-HMAC-SHA256 hashes with a per-student salt. **No
password is ever written to a file** — a forgotten one is reset, not
recovered. `--all --password X` gives every student the same password,
which is convenient for the first week and a bad idea afterwards: anyone
who knows one can sign in as anybody.

To give each student their own password, and print a list to hand out:

```bash
python scripts/set_student_password.py --all --print
```

That sets a random password for every student and prints the list. The
printed list is the only place the passwords exist — save it somewhere
private, and delete it afterwards. A student who forgets theirs gets a
new one:

```bash
python scripts/set_student_password.py --sid 20233004 --print
```

**A student with no password set cannot sign in.** That is deliberate: a
roster that lists a student without a password is a student the teacher
has not issued a password to yet, not a student with an empty password.

Two files are deliberately **not** committed, and are in `.gitignore`:

- `data/roster.json` — the students' names and their password hashes.
- `data/activity_log.jsonl` — who signed in, what they asked, when.

Both are set on a deployed server through the environment instead
(`MAKGEO_ROSTER_PATH` or `MAKGEO_ROSTER_JSON`, and `MAKGEO_ACTIVITY_LOG`).

The teacher gets a **"Who has used the site"** panel: who has signed in, how
many questions they asked, how many essays they wrote, and when they were
last seen, broken down by class. The server refuses the request from
anyone who is not the teacher, so the data is not merely hidden in the page
— it is not served.

`scripts/test_roster.py` covers the sign-in rules (41 checks).

---

## Deploying

There are two deployments, and they are different things.

### The live site (the working application)

The FastAPI app, with the chatbot and the essay generator working. It runs
in a container, so it needs a host that runs one — Render, Fly, Railway,
or anything else that takes a Dockerfile. The repository has what it
needs:

- `Dockerfile` — a slim `python:3.12-slim` image that runs uvicorn on
  `${PORT:-10000}`.
- `render.yaml` — a Render blueprint. It asks for `MAKGEO_TEACHER_KEY`,
  `MINIMAX_API_KEY`, `MAKGEO_PASSWORD` and `MAKGEO_ROSTER_PATH`; the
  values marked `sync: false` are prompted for, not committed.
- `Procfile` — for hosts that use one.
- `GET /healthz` — the platform's health check. It touches nothing: no
  knowledge base, no language model, no session.

The image carries the data the site reads at runtime — `kb.json`,
`curriculum.json`, `mc_bank.json`, `news.json`, the question images and
the official exam images. The 55 MB of HKEAA briefing decks in
`data/papers` are removed from the image, because the site does not read
them.

The app is container-safe: it resolves everything relative to the
repository, and a missing `~/.hermes/.env` is a normal state rather than
an error, because on a server the key comes from the environment.

### The static copy (GitHub Pages)

`https://davidtwmak-maker.github.io/MakGeography/` — the read-only half
of the site: MC Drilling, Notes, News Corner and the essay topic tree,
built by `.github/workflows/pages.yml` into plain HTML and JSON. It is a
stable address that never changes, which a Cloudflare quick tunnel cannot
promise.

Ask and generating an essay are **not** in the static copy, because both
need a language model. Those panels say so and point the student at the
live site rather than failing silently.

### On the teacher's Mac

`scripts/install_launchd.sh` installs two `launchd` jobs:

- `com.makgeo.app` — the server, restarted if it crashes
- `com.makgeo.news` — refreshes the news feed every hour

```bash
export MAKGEO_PASSWORD='your-password'
./scripts/install_launchd.sh
```

The script reads `MINIMAX_API_KEY` from the environment, or from
`~/.hermes/.env`. Neither the password nor the key is written into the repo.

### The live address

`scripts/install_tunnel.sh` installs a third `launchd` job,
`com.makgeo.tunnel`, which publishes the site:

```bash
./scripts/install_tunnel.sh
```

The site lives at:

```
https://makgeography.serveousercontent.com
```

That address is **permanent**. Serveo reserves the subdomain against the
SSH key at `~/.ssh/serveo_rsa`, so the tunnel can restart and the URL is
unchanged.

**Serveo now shows a warning interstitial to real browsers.** A student
opening the address sees a "Serveo - Warning" page and a "Continue to
Site" button instead of the site — the interstitial is served by
Serveo's edge, before the request reaches the app, so the app cannot
redirect around it. Clicking through once sets a cookie and the site
works after that, but the first visit looks broken.

So a **second tunnel runs alongside it**: a Cloudflare quick tunnel,
which serves the site directly with no interstitial. Its hostname is
random and changes on every restart, so it is not an address to keep —
it is the one to hand to a student who needs the site right now:

```bash
cat ~/.hermes/logs/makgeo-url-cf.txt
```

The Serveo address remains the permanent one, written to
`~/.hermes/logs/makgeo-url.txt`. For an address that is both permanent
**and** free of interstitials, deploy the container (see `render.yaml`)
rather than tunnelling from the teacher's Mac.

### What is and is not public

The repo is public. The **code** is public; the **vault notes are not** —
they are not committed. `data/kb.json` is a derived artefact of the
teacher's own notes and is committed so the site can run standalone; if
that changes, remove it from git and add it to `.gitignore`.

The student roster and the activity log are also not committed, because
they hold the students' names and what they asked.

---

## Licence

Code: MIT — see `LICENSE`.

Notes and question content: © David Mak, all rights reserved. They are included
for classroom use by MakGeography students and may not be redistributed.
