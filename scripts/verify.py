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
