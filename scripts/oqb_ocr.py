#!/usr/bin/env python3
"""OCR every OQB geography question image with macOS Vision.

Writes  data/hkeaa_oqb/ocr/<subject>.json  with, per question:
  stem_text, options[{text, image}], answer, and the source image paths.

Images are upscaled 2x before recognition (Vision is markedly more accurate
on the small exam-text PNGs), and English/Chinese language hints are set.
"""
import pathlib
BASE = pathlib.Path(__file__).resolve().parent.parent
import json
import os
import sys
import threading
import time
from collections import defaultdict

import Quartz
import Vision
from Foundation import NSURL

BASE = BASE / "data" / "hkeaa_oqb"
_lock = threading.Lock()
_stats = {"done": 0, "err": 0, "empty": 0}


def ocr_image(path, scale=2.0):
    """Return a list of text lines, or [] on failure."""
    try:
        url = NSURL.fileURLWithPath_(path)
        src = Quartz.CGImageSourceCreateWithURL(url, None)
        if src is None:
            return []
        cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
        if cg is None:
            return []
        w = Quartz.CGImageGetWidth(cg)
        h = Quartz.CGImageGetHeight(cg)
        nw, nh = int(w * scale), int(h * scale)
        cs = Quartz.CGColorSpaceCreateDeviceRGB()
        ctx = Quartz.CGBitmapContextCreate(
            None, nw, nh, 8, 0, cs, Quartz.kCGImageAlphaPremultipliedFirst)
        Quartz.CGContextSetInterpolationQuality(ctx, Quartz.kCGInterpolationHigh)
        Quartz.CGContextScaleCTM(ctx, scale, scale)
        Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, w, h), cg)
        big = Quartz.CGBitmapContextCreateImage(ctx)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)
        req.setUsesLanguageCorrection_(True)
        req.setRecognitionLanguages_(["en-HK", "en-US", "zh-HK"])
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(big, None)
        ok, _ = handler.performRequests_error_([req], None)
        res = req.results() or []
        return [r.topCandidates_(1)[0].string() for r in res]
    except Exception:
        return []


def clean(lines):
    """Normalise OCR output: strip, drop blanks, tidy the common artefacts."""
    out = []
    for l in lines:
        s = " ".join(l.split())
        if not s:
            continue
        out.append(s)
    return out


def process(args):
    subject, qid, stem_rel, choice_rels, outdir = args
    stem_lines = clean(ocr_image(stem_rel))
    opts = []
    for rel in choice_rels:
        opts.append(clean(ocr_image(rel)))
    rec = {"qid": qid, "stem": stem_lines, "options": opts}
    with _lock:
        _stats["done"] += 1
        if not stem_lines:
            _stats["empty"] += 1
        d = _stats["done"]
        if d % 250 == 0:
            print(f"  {d} OCR'd, {len(opts)} opts", flush=True)
    return rec


def main():
    subject = sys.argv[1] if len(sys.argv) > 1 else "geog"
    manifest = json.load(open(f"{BASE}/hkeaa_mc_manifest.json", encoding="utf-8"))
    raw = json.load(open(f"{BASE}/_raw/{subject}.json", encoding="utf-8"))
    by_id = {r["id"]: r for r in raw}

    jobs = []
    for m in manifest:
        if m["subject"] != subject:
            continue
        qid = m["en_id"] or m["zh_id"]
        row = by_id.get(qid)
        if not row:
            continue
        stem = os.path.join(BASE, subject, str(qid), row.get("content") or "")
        choices = sorted(row.get("choices") or [], key=lambda c: c.get("seq") or 0)
        cfiles = [os.path.join(BASE, subject, str(qid), c.get("content") or "")
                  for c in choices]
        jobs.append((subject, qid, stem, cfiles, None))

    print(f"OCR {len(jobs)} {subject} questions", flush=True)
    t0 = time.time()
    import concurrent.futures as cf
    recs = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for rec in ex.map(process, jobs):
            recs.append(rec)

    out = {str(r["qid"]): {"stem": r["stem"], "options": r["options"]} for r in recs}
    os.makedirs(f"{BASE}/ocr", exist_ok=True)
    with open(f"{BASE}/ocr/{subject}.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"done: {_stats['done']} questions, {_stats['empty']} empty stems, "
          f"{time.time()-t0:.0f}s -> {BASE}/ocr/{subject}.json")


if __name__ == "__main__":
    main()
