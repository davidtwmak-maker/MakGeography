#!/usr/bin/env python3
"""Build a static copy of the site for GitHub Pages.

The live site is FastAPI (app/main.py) running on this Mac behind a
Cloudflare tunnel. GitHub Pages can only serve static files, so this
script renders the read-only parts of the site into plain HTML and JSON:

    MC Drilling    the question bank, the images, the map extracts
    Notes          the curriculum-scaffolded notes
    News Corner    the collected news
    Essay tree     the sub-topics the essay picker offers

The two features that need a language model - Ask and Generate an essay -
cannot be static. They are left pointing at the live server, and the
static copy says so plainly instead of pretending to work.

The output goes to site/, which GitHub Pages publishes. Paths are written
relative to the site root so the same build works on
davidtwmak-maker.github.io/MakGeography/ and on a domain root.

Usage:  python scripts/build_static_site.py
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATIC = ROOT / "static"
TEMPLATES = ROOT / "templates"
OUT = ROOT / "site"

# Where the live server lives. The static build borrows the read-only
# JSON from it so the two never drift apart.
LIVE = "http://127.0.0.1:8781"


def load_json(name, default):
    p = DATA / name
    if not p.is_file():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def build_mc_json():
    """The question bank, in the shape /api/mc returns."""
    bank = load_json("mc_bank.json", {"questions": []})
    qs = bank.get("questions", [])

    # The API derives an id when one is missing, and sorts official
    # questions first. Do the same here so the static copy matches.
    import hashlib

    for q in qs:
        if not q.get("id"):
            q["id"] = f"{q.get('subtopic', 'gen')}-" + hashlib.sha1(
                q.get("stem", "").encode()).hexdigest()[:8]

    def sort_key(q):
        return (0 if q.get("official") else 1, -(q.get("year") or 0), q.get("q") or 0)

    qs = sorted(qs, key=sort_key)
    topics = sorted({t for q in qs for t in (q.get("topics") or []) if t})
    official_total = sum(1 for q in qs if q.get("official"))
    return {"questions": qs, "total": len(qs), "topics": topics,
            "official_total": official_total}


def build_notes_json():
    """The notes tree, in the shape /api/notes returns.

    This mirrors app/main.py's api_notes exactly: the curriculum is the
    skeleton and the note content is matched into each leaf by the same
    hints, through the same matcher.
    """
    sys.path.insert(0, str(ROOT))
    from app.main import get_kb, get_matcher  # noqa: E402

    cur = load_json("curriculum.json", {"electives": []})
    matcher = get_matcher()

    electives = []
    for el in cur.get("electives", []):
        subqs = []
        for sq in el.get("subquestions", []):
            leaves = []
            for leaf in sq.get("leaves", []):
                content = matcher.match(matcher.hints_for(leaf),
                                         leaf.get("title", ""))
                leaves.append({
                    "id": leaf.get("id"),
                    "title": leaf.get("title"),
                    "summary": leaf.get("summary"),
                    "content": content,
                })
            subqs.append({"number": sq.get("number"), "title": sq.get("title"),
                          "leaves": leaves})
        electives.append({
            "code": el.get("code", ""),
            "title": el.get("title"),
            "module": el.get("module"),
            "question": el.get("question"),
            "subquestions": subqs,
        })

    kb = get_kb()
    return {"electives": electives, "topics": kb.topics, "kb_topics": kb.topics}


def build_essay_tree_json():
    """The essay picker tree, in the shape /api/essay/tree returns."""
    sys.path.insert(0, str(ROOT))
    from app import essay as essay_mod  # noqa: E402

    cur = load_json("curriculum.json", {"electives": []})
    out = []
    for el in cur.get("electives", []):
        code = el.get("code", "").upper()
        if code not in essay_mod.ESSAY_ELECTIVES:
            continue
        subqs = []
        for sq in el.get("subquestions", []):
            leaves = [{"id": l.get("id"), "title": l.get("title")}
                      for l in sq.get("leaves", []) if l.get("id")]
            if leaves:
                subqs.append({"number": sq.get("number"), "title": sq.get("title"),
                              "leaves": leaves})
        out.append({"code": code, "title": el.get("title"), "subquestions": subqs})

    # The full shape /api/essay/tree returns. The front end reads the
    # command lists and the mark options from here, so a build that
    # leaves them out shows empty dropdowns.
    return {
        "electives": out,
        "marks": list(essay_mod.MARK_OPTIONS),
        # Two command lists, one per half of the essay. The Part (b) list
        # carries the judgement commands; the Part (a) list carries the
        # knowledge-and-mechanism commands.
        "commands_a": [{"key": k, "label": v}
                       for k, v in essay_mod.PART_A_COMMANDS.items()],
        "commands_b": [{"key": k, "label": v}
                       for k, v in essay_mod.PART_B_COMMANDS.items()],
    }


def build_kb_status_json():
    kb = load_json("kb.json", {"docs": []})
    docs = kb.get("docs", [])
    chunks = sum(len(d.get("chunks", [])) for d in docs)
    topics = sorted({d.get("topic") for d in docs if d.get("topic")})
    return {"docs": len(docs), "chunks": chunks, "topics": topics,
            "built_at": kb.get("built_at", "")}


def build_news_json():
    items = load_json("news.json", [])
    meta = load_json("news_meta.json", {})
    return {"items": items, "updated_at": meta.get("updated_at")}


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1. The API responses, as static JSON files.
    write_json(OUT / "api" / "mc.json", build_mc_json())
    write_json(OUT / "api" / "notes.json", build_notes_json())
    write_json(OUT / "api" / "news.json", build_news_json())
    write_json(OUT / "api" / "kb" / "status.json", build_kb_status_json())
    write_json(OUT / "api" / "essay" / "tree.json", build_essay_tree_json())

    # 2. The question images and the map extracts.
    #
    # The bank stores its paths as "geog/<row-id>/<file>" and
    # "geog/_attachments/_files/<file>", so the "geog" directory has to be
    # copied whole - the paths in the bank must keep matching the layout
    # on disk.
    oqb = DATA / "hkeaa_oqb"
    if oqb.is_dir():
        for item in oqb.iterdir():
            if item.name == "_raw":
                continue
            dest = OUT / "oqb-media" / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
    qi = DATA / "question_images"
    if qi.is_dir():
        shutil.copytree(qi, OUT / "question-images")

    # 3. The stylesheet and the script.
    shutil.copytree(STATIC, OUT / "static")

    # 4. The page itself.
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    # Rewrite the absolute paths so the build works under a sub-path
    # (davidtwmak-maker.github.io/MakGeography/) as well as at a root.
    html = html.replace('href="/static/style.css"', 'href="static/style.css"')
    html = html.replace('src="/static/app.js"', 'src="static/app.js"')

    # The static build has no sessions, so the sign-out form is meaningless.
    # It sits inside a Jinja {% if password_required %} block, which the
    # static build never renders, so the whole block goes.
    html = re.sub(r"\{%\s*if password_required\s*%\}.*?\{%\s*endif\s*%\}",
                  "", html, flags=re.S)

    # A marker the script reads to know it is running from a static build.
    # It must come BEFORE app.js, because app.js reads it on load.
    html = html.replace(
        '<script src="static/app.js"></script>',
        '<script>window.MAKGEO_STATIC = true;</script>\n'
        '<script src="static/app.js"></script>')
    (OUT / "index.html").write_text(html, encoding="utf-8")

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"static build written to {OUT}")
    print(f"  {sum(1 for f in OUT.rglob('*') if f.is_file())} files, {total/1e6:.1f} MB")


if __name__ == "__main__":
    main()
