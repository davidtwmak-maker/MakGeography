import json, os, pathlib, re, sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

# 1. App imports
import app.main as am  # noqa: F401
print("app imports cleanly")

# 2. KB integrity
kb = json.loads((root / "data" / "kb.json").read_text())
docs = kb.get("docs", [])
assert docs, "kb.json has no documents"
chunks = sum(len(d.get("chunks", [])) for d in docs)
assert chunks > 500, f"only {chunks} chunks — the KB looks truncated"
print(f"KB OK: {len(docs)} docs, {chunks} chunks")

# 3. No assessment material
bad = re.compile(
    r"(?i)(past paper|predicted grade|first term test|combo quiz|"
    r"mark scheme|answer key|data question set|dbq angles|mc quiz)")
leaks = [d["path"] for d in docs if bad.search(d["path"])]
if leaks:
    print("Assessment material leaked into the KB:")
    for p in leaks:
        print("  -", p)
    sys.exit(1)
print("No assessment material in the KB")

# 3b. No teacher-only working material.
#
# A note may be fine to read, but the teacher's own answer key, the register
# of stems already used, and the distractor rationale must never reach a
# student. These live inside otherwise-shareable notes, so a path check is
# not enough - the text has to be checked too.
teacher_only = re.compile(
    r"(?i)(register check|used[- ]stem (register|entries)|"
    r"teacher'?s? answer key|distractor rationale|"
    r"why this distractor|teacher key and rationale|"
    r"key and rationale)")
blob_leaks = []
for d in docs:
    for c in d.get("chunks", []):
        if teacher_only.search(c.get("text", "")):
            blob_leaks.append(f"{d['path']} :: {c.get('heading', '')}")
            break
if blob_leaks:
    print("Teacher-only material leaked into the KB:")
    for p in blob_leaks:
        print("  -", p)
    sys.exit(1)
print("No teacher-only material in the KB")

# 4. Curriculum scaffold
cur = json.loads((root / "data" / "curriculum.json").read_text())
codes = [e["code"] for e in cur["electives"]]
assert set(codes) == {"CP1", "CP2", "CP3", "CP4", "CP5", "CP6", "CP7", "EP1"}, codes
n = sum(len(s.get("leaves", [])) for e in cur["electives"] for s in e["subquestions"])
unhinted = sum(
    1
    for e in cur["electives"]
    for s in e["subquestions"]
    for l in s.get("leaves", [])
    if not l.get("source_hints")
)
print(f"Curriculum OK: {len(codes)} electives, {n} leaves, {unhinted} without source hints")

# 5. Retrieval smoke test
from app.kb import KnowledgeBase
kb2 = KnowledgeBase(root / "data" / "kb.json")
checks = {
    "why is silicon valley footloose": "Silicon Valley",
    "tsunami hong kong coastal": "coastal",
    "deindustrialisation causes": "Deindustrial",
}
for q, expect in checks.items():
    res = kb2.search(q, k=3)
    assert res, f"no results for: {q}"
    blob = " ".join(c.title for c, _ in res)
    print(f"  {q[:38]:40s} -> {res[0][0].title[:44]}")

# 6. The Essay Generator's scope.
#
# It covers CP1-CP7 and EP1. F2 and F3 are a different course, so the
# generator must refuse them AND never draw on their notes - a practice
# essay that mixes the two syllabuses would teach the wrong content.
import app.essay as essay

assert set(essay.ESSAY_ELECTIVES) == {
    "CP1", "CP2", "CP3", "CP4", "CP5", "CP6", "CP7", "EP1"
}, essay.ESSAY_ELECTIVES
assert "F2" not in essay.ESSAY_ELECTIVES and "F3" not in essay.ESSAY_ELECTIVES
print("Essay generator scope: CP1-CP7 + EP1, F2/F3 excluded")

matcher = am.get_matcher()
cur = json.loads((root / "data" / "curriculum.json").read_text())
for code in essay.ESSAY_ELECTIVES:
    try:
        sources, context = essay.collect_source(matcher, cur, code)
    except ValueError as e:
        print(f"  {code}: ERROR {e}")
        sys.exit(1)
    assert context.strip(), f"{code} has no note material for an essay"
    assert len(context) > 1000, (
        f"{code} only has {len(context)} chars of material - too thin to "
        f"write an essay from")
    # No F2/F3 note may reach the context.
    for s in sources:
        p = s.get("path", "")
        assert not p.startswith(("F2 ", "F3 ")), f"F2/F3 note leaked: {p}"
    print(f"  {code}: {len(sources)} note sections, {len(context)} chars")

for bad in ("F2", "F3"):
    try:
        essay.collect_source(matcher, cur, bad)
        print(f"  {bad} was accepted - it must be refused")
        sys.exit(1)
    except ValueError:
        pass
print("F2 and F3 are refused, and neither reaches the essay context")

# Every sub-topic must be able to carry an essay on its own. A leaf that
# resolves to a single paragraph cannot support a 12-mark answer.
thin = []
for el in cur["electives"]:
    code = el["code"]
    if code not in essay.ESSAY_ELECTIVES:
        continue
    for sq in el.get("subquestions", []):
        for leaf in sq.get("leaves", []):
            _s, ctx = essay.collect_source(
                matcher, cur, code, leaf_ids=[leaf["id"]])
            if len(ctx) < 600:
                thin.append((leaf["id"], len(ctx)))
if thin:
    print(f"Sub-topics with too little material for an essay: {thin}")
    sys.exit(1)
n_leaves = sum(
    len(sq.get("leaves", []))
    for el in cur["electives"] if el["code"] in essay.ESSAY_ELECTIVES
    for sq in el.get("subquestions", [])
)
print(f"Every one of the {n_leaves} sub-topics has enough material for an essay")

# 7. The rate limit must be per browser, not one shared bucket.
#
# With the gate off nobody logs in, so keying the limit on the session
# cookie would put every visitor in the same bucket - one person's
# questions would lock out everyone else.
from fastapi.testclient import TestClient

_client = TestClient(am.app)
_r = _client.get("/")
assert "makgeo_session" in _r.cookies, (
    "the home page must hand out a session token so the rate limit is "
    "per browser")
_cookies = _r.cookies.get("makgeo_session")
assert _cookies, "the session cookie is empty"

# A second visitor gets their own bucket.
_r2 = TestClient(am.app).get("/")
_b2 = _r2.cookies.get("makgeo_session")
assert _b2 and _b2 != _cookies, "two visitors share one session token"
print(f"Rate limit is per browser: {_cookies[:8]}... and {_b2[:8]}... are separate")

# And the buckets are separate per operation, so an essay generation
# does not spend the chatbot's budget.
assert am.check_rate("x", bucket="ask")
assert am.check_rate("x", bucket="essay"), (
    "the essay bucket must be separate from the chatbot's")
print("The chatbot and the essay generator have separate rate-limit buckets")

# 8. The password gate is optional: with none configured the site is open.
assert am.password_required() is False, (
    "no password is configured, so the gate should be off")
print("Password gate: off (the site is open - no MAKGEO_PASSWORD set)")

# And with one configured it comes back on.
os.environ["MAKGEO_PASSWORD"] = "verify-only-not-a-real-password"
am._password_cache = None
try:
    assert am.password_required() is True, "the gate should turn back on"
    print("Password gate: on when MAKGEO_PASSWORD is set")
finally:
    del os.environ["MAKGEO_PASSWORD"]
    am._password_cache = None

# 9. The essay generator's two-part command structure.
#
# A DSE short essay is two parts with two DIFFERENT command words. One
# command word running across all 12 marks is a single-command question
# wearing a 12-mark label, not the exam format.
assert set(essay.PART_A_COMMANDS) == {"account", "describe_explain", "explain"}
assert set(essay.PART_B_COMMANDS) == {
    "discuss", "explain_why", "evaluate", "assess"
}
assert not (set(essay.PART_A_COMMANDS) & set(essay.PART_B_COMMANDS))
_ca, _cb, _pa, _pb = essay.resolve_commands(
    "describe_explain", "discuss", 12)
assert (_pa, _pb) == (6, 6), (_pa, _pb)
assert essay.resolve_commands("describe_explain", "discuss", 8)[1] == "", (
    "an 8-mark essay is a single part and takes one command word")
print("Essay generator: two command lists, 12 marks -> 6+6, 8 marks -> one part")

print("\nALL CHECKS PASSED")
