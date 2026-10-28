#!/usr/bin/env python3
"""Download every HKEAA MC question on the OQB platform, with images.

Stage 1  fetch all question rows per subject (metadata + content + SAS URLs)
Stage 2  download every image (stem + choices) to disk
Stage 3  write a clean manifest (JSON + CSV) grouped by question

Usage:  oqb_download.py [--out DIR] [--subjects a,b,c] [--no-images]
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent
import argparse
import concurrent.futures as cf
import json
import os
import sys
import threading
import time
from collections import defaultdict

sys.path.insert(0, "/Users/davidhermes/.hermes/cache/scratch")
from oqb_api import search, fetch_blob, load_token

SUBJECTS = ["geog", "bafs", "bio", "chem", "cit", "econ", "math", "pe", "phy", "ths"]
_lock = threading.Lock()
_stats = {"images": 0, "bytes": 0, "errors": 0}


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def fetch_rows(subject, page=800):
    """All rows for one subject, paged."""
    rows = []
    offset = 0
    while True:
        chunk = search({"publisher_code": ["HKEAA"], "subject_code": [subject]},
                       limit=page, offset=offset, with_content=1)
        if not isinstance(chunk, list) or not chunk:
            break
        rows.extend(chunk)
        log(f"  {subject}: {len(rows)} rows (offset {offset})")
        if len(chunk) < page:
            break
        offset += page
    return rows


def collect_images(rows):
    """Map image filename -> (question id, role, url). Dedupe by filename+id.

    Also returns attachments (map extracts, PDFs, data files) that some
    questions reference; these are the shared paper figures.
    """
    imgs = {}
    atts = []
    for r in rows:
        qid = r.get("id")
        stem = r.get("content")
        url = r.get("url")
        if stem and url:
            imgs[(qid, "stem")] = (stem, url)
        for c in (r.get("choices") or []):
            if c.get("content") and c.get("url"):
                imgs[(qid, f"choice{c.get('seq')}")] = (c["content"], c["url"])
        att_map = r.get("attachment") or {}
        att_urls = r.get("attachment_url") or {}
        for label, fname in att_map.items():
            if fname and label in att_urls:
                atts.append((qid, label, fname, att_urls[label]))
    return imgs, atts


def download_attachment(args):
    subject, qid, label, fname, url, outdir = args
    safe = "".join(ch for ch in label if ch.isalnum() or ch in "._- ")[:40] or "attachment"
    sub = os.path.join(outdir, subject, "_attachments", str(qid))
    out = os.path.join(sub, fname)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        with _lock:
            _stats["images"] += 1
        return True
    try:
        n = fetch_blob(url, out)
        with _lock:
            _stats["images"] += 1
            _stats["bytes"] += n
        return True
    except Exception:
        with _lock:
            _stats["errors"] += 1
        return False


def download_one(args):
    subject, qid, role, fname, url, outdir = args
    out = os.path.join(outdir, subject, str(qid), fname)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        with _lock:
            _stats["images"] += 1
        return True
    try:
        n = fetch_blob(url, out)
        with _lock:
            _stats["images"] += 1
            _stats["bytes"] += n
        return True
    except Exception:
        with _lock:
            _stats["errors"] += 1
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=BASE / "data" / "hkeaa_oqb")
    ap.add_argument("--subjects", default=",".join(SUBJECTS))
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    subjects = [s.strip() for s in args.subjects.split(",") if s.strip()]
    outdir = os.path.abspath(args.out)
    os.makedirs(outdir, exist_ok=True)
    rawdir = os.path.join(outdir, "_raw")
    os.makedirs(rawdir, exist_ok=True)

    all_rows = {}
    for s in subjects:
        log(f"fetching {s} ...")
        try:
            rows = fetch_rows(s)
        except Exception as e:
            log(f"  FAILED {s}: {e}")
            continue
        all_rows[s] = rows
        with open(os.path.join(rawdir, f"{s}.json"), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
        log(f"  {s}: {len(rows)} rows saved")

    if not all_rows:
        log("nothing fetched")
        return 1

    if not args.no_images:
        jobs = []
        att_jobs = []
        for s, rows in all_rows.items():
            imgs, atts = collect_images(rows)
            for (qid, role), (fname, url) in imgs.items():
                jobs.append((s, qid, role, fname, url, outdir))
            for (qid, label, fname, url) in atts:
                att_jobs.append((s, qid, label, fname, url, outdir))
        log(f"downloading {len(jobs)} images + {len(att_jobs)} attachments "
            f"with {args.workers} workers ...")
        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            done = 0
            alljobs = jobs + att_jobs
            for ok in ex.map(lambda j: (download_attachment(j) if j in att_jobs
                                        else download_one(j)), alljobs):
                done += 1
                if done % 500 == 0:
                    log(f"  {done}/{len(alljobs)}  {_stats['images']} ok, "
                        f"{_stats['errors']} err, {_stats['bytes']/1e6:.1f} MB, "
                        f"{time.time()-t0:.0f}s")
        log(f"images done: {_stats['images']} ok, {_stats['errors']} err, "
            f"{_stats['bytes']/1e6:.1f} MB")

    # manifest
    manifest = []
    for s, rows in all_rows.items():
        by_q = defaultdict(list)
        for r in rows:
            by_q[r.get("qcode")].append(r)
        for qcode, items in by_q.items():
            en = next((x for x in items if x.get("lang") == "en"), None)
            zh = next((x for x in items if x.get("lang") == "zh"), None)
            src = en or zh
            manifest.append({
                "qcode": qcode,
                "subject": src.get("subject_code"),
                "publisher": src.get("publisher_code"),
                "year": src.get("year"),
                "question_no": src.get("question_no"),
                "description": src.get("description"),
                "itype": src.get("itype"),
                "difficulty": src.get("eaa_difficulty_code"),
                "nss": src.get("nss"),
                "topic_code": src.get("topic_code") or [],
                "dimension_code": src.get("dimension_code") or [],
                "is_dse": src.get("is_dse"),
                "en_id": en.get("id") if en else None,
                "zh_id": zh.get("id") if zh else None,
                "en_answer": en.get("suggested_answer") if en else None,
                "zh_answer": zh.get("suggested_answer") if zh else None,
                "en_model_answer": en.get("model_answer") if en else None,
                "suggested_score": src.get("suggested_score"),
                "suggested_time": src.get("suggested_time"),
                "has_en": bool(en),
                "has_zh": bool(zh),
                "n_choices": len((en or src).get("choices") or []),
                "stem_file": (en or src).get("content"),
                "stem_type": (en or src).get("content_type"),
                "attachments": (en or src).get("attachment") or {},
                "package_id": src.get("package_id") or [],
            })
    manifest.sort(key=lambda x: (x["subject"], x["year"] or 0, x["question_no"] or 0, x["qcode"] or ""))
    with open(os.path.join(outdir, "hkeaa_mc_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    import csv
    if manifest:
        with open(os.path.join(outdir, "hkeaa_mc_manifest.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
            w.writeheader()
            for m in manifest:
                row = dict(m)
                for k in ("topic_code", "dimension_code", "package_id"):
                    row[k] = ";".join(map(str, row[k] or []))
                row["attachments"] = "; ".join(f"{k}={v}" for k, v in (row.get("attachments") or {}).items())
                w.writerow(row)

    from collections import Counter
    print()
    print("=== SUMMARY ===")
    print("questions:", len(manifest))
    for s, c in sorted(Counter(m["subject"] for m in manifest).items()):
        print(f"  {s:6} {c}")
    print("by year:")
    for y, c in sorted(Counter(m["year"] for m in manifest).items()):
        print(f"  {y} {c}")
    print("images:", _stats["images"], "errors:", _stats["errors"],
          f"bytes: {_stats['bytes']:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
