import json, pathlib, re, sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

# 1. App imports
import app.main  # noqa: F401
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

print("\nALL CHECKS PASSED")
