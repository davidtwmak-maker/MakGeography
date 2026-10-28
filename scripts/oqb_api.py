#!/usr/bin/env python3
"""OQB question-bank downloader.

Session: a JWT obtained from the logged-in browser (the API accepts the token
with no session cookie). Calls the OQB API exactly the way the SPA does:
POST /api/<action>, form-encoded, arrays as key[i], criteria/opts nested.

Images come from the Azure blob store using the per-question SAS URLs the
API returns; the "rsct= " parameter carries a literal space and must be
percent-encoded as %20 or the SAS signature check fails.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://oqb.edcity.hk"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")

TOKEN_FILE = "/Users/davidhermes/.hermes/cache/scratch/oqb_token.txt"


def load_token():
    with open(TOKEN_FILE, encoding="utf-8") as fh:
        return fh.read().strip()


def mk(o):
    """Serialise like the app's module 95535: arrays -> key[i], dicts -> key[k]."""
    parts = []

    def add(obj, pfx):
        for k, v in obj.items():
            key = f"{pfx}[{k}]" if pfx else k
            if v is None:
                continue
            if isinstance(v, (list, tuple)):
                for i, x in enumerate(v):
                    parts.append((f"{key}[{i}]", x))
            elif isinstance(v, dict):
                add(v, key)
            else:
                parts.append((key, v))

    add(o, "")
    return urllib.parse.urlencode(parts)


def api(action, payload, token=None):
    body = mk({"app": "OQB", "token": token or load_token(), **payload})
    req = urllib.request.Request(
        f"{BASE}/api/{action}", data=body.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": UA,
                 "Referer": BASE + "/teacher/tests",
                 "Origin": BASE,
                 "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=180) as r:
        txt = r.read().decode("utf-8", "replace")
    j = json.loads(txt)
    if not j.get("success"):
        raise RuntimeError(f"{action}: {j.get('error')}")
    return j.get("result")


def search(criteria, limit=500, offset=0, with_content=1):
    return api("search_questions", {
        "criteria": criteria,
        "opts": {"rand": 0, "limit": limit, "offset": offset,
                 "with_content": with_content},
    })


def fetch_blob(url, out_path, retries=3):
    """Download an Azure SAS URL. The 'rsct= ' param needs %20."""
    if "rsct= " in url:
        url = url.replace("rsct= ", "rsct=%20")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Referer": BASE + "/"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if not data:
                raise RuntimeError("empty body")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as fh:
                fh.write(data)
            return len(data)
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return 0


if __name__ == "__main__":
    tok = load_token()
    print("token len:", len(tok))
    r = search({"publisher_code": ["HKEAA"], "subject_code": ["geog"]}, limit=3)
    print("geog sample:", [(x.get("qcode"), x.get("lang"), x.get("year")) for x in r])
