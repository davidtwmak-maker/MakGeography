#!/usr/bin/env python3
"""Inventory every HKEAA question available on OQB, by subject and year."""
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/davidhermes/.hermes/cache/scratch")
from oqb_api import search, load_token

SUBJECTS = ["geog", "bafs", "bio", "chem", "cit", "econ", "math", "chs", "eng", "lib", "it", "cat"]

out = {"by_subject": {}, "subjects_present": [], "errors": {}}

for code in SUBJECTS:
    try:
        res = search({"publisher_code": ["HKEAA"], "subject_code": [code]},
                     limit=5000, with_content=0)
    except Exception as e:
        out["errors"][code] = str(e)[:200]
        continue
    if not isinstance(res, list):
        out["errors"][code] = f"non-list: {str(res)[:80]}"
        continue
    by_year = Counter()
    by_lang = Counter()
    by_type = Counter()
    by_q = defaultdict(set)
    for x in res:
        by_year[x.get("year")] += 1
        by_lang[x.get("lang")] += 1
        by_type[x.get("itype")] += 1
        by_q[x.get("qcode")].add(x.get("lang"))
    out["by_subject"][code] = {
        "rows": len(res),
        "distinct_qcodes": len(by_q),
        "by_year": {str(k): v for k, v in sorted(by_year.items(), key=lambda kv: str(kv[0]))},
        "by_lang": dict(by_lang),
        "by_itype": dict(by_type),
    }
    if res:
        out["subjects_present"].append(code)

print(json.dumps(out, indent=1, ensure_ascii=False))
with open("/Users/davidhermes/.hermes/cache/scratch/oqb_inventory.json", "w") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
