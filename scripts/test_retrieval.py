import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.kb import KnowledgeBase

kb = KnowledgeBase(pathlib.Path(__file__).resolve().parent.parent / "data" / "kb.json")
print("docs", kb.meta.get("n_docs"), "chunks", len(kb.chunks))
print("topics", kb.topics)
for q in [
    "why is silicon valley footloose",
    "tsunami formation and hong kong coastal management",
    "why are factory units bigger in dongguan than hong kong",
    "explain deindustrialisation",
    "weathering in hong kong granite",
]:
    res = kb.search(q, k=3)
    print()
    print("Q:", q)
    for c, s in res:
        print(f"   {s:6.2f}  {c.title[:52]:52s} | {c.heading[:44]}")
