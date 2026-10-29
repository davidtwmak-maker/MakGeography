"""Test that the static build points at the live site, and that it does.

The static copy is published to GitHub Pages, which cannot answer a
question - the Ask and essay panels there say so and link to the live
site instead.

The link used to be a hostname written into static/app.js. A Cloudflare
quick tunnel changes its hostname on every restart, so that link went
dead while the page still looked fine: the student clicked "Open
MakGeography" and nothing happened.

So the address is read at build time and injected into the page, and
nothing in the source may name a tunnel hostname.
"""

import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build_static_site.py"

failures = []
checks = 0


def check(label, ok, detail=""):
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


print("1. No tunnel hostname is written into the source")
# A trycloudflare hostname in the source is a dead link waiting to happen.
tracked = subprocess.run(
    ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
hits = []
for rel in tracked:
    path = ROOT / rel
    if not path.is_file() or path.suffix not in (".js", ".html", ".py", ".md"):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for m in re.finditer(r"[a-z0-9-]+\.trycloudflare\.com", text):
        # The installer and the README name the pattern, not a live host.
        line_no = text[:m.start()].count("\n") + 1
        hits.append(f"{rel}:{line_no}")
check("no hardcoded trycloudflare hostname in tracked source", not hits,
      str(hits[:5]))

print("2. The front end reads the address instead of naming it")
app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
check("app.js reads window.MAKGEO_LIVE_URL",
      "window.MAKGEO_LIVE_URL" in app_js)
check("app.js has no literal tunnel hostname",
      "trycloudflare.com" not in app_js)
check("both static panels use the injected address",
      app_js.count("LIVE_URL") >= 3,
      f"LIVE_URL appears {app_js.count('LIVE_URL')} times")

print("3. The build injects the live address")
check("the build script can find an address",
      "read_live_url" in BUILD.read_text(encoding="utf-8"))

print("4. The built page carries a working address")
site_index = ROOT / "site" / "index.html"
if not site_index.is_file():
    print("  --   site/ is not built; run scripts/build_static_site.py")
else:
    html = site_index.read_text(encoding="utf-8")
    m = re.search(r'window\.MAKGEO_LIVE_URL = "([^"]*)"', html)
    check("the built page sets MAKGEO_LIVE_URL", bool(m))
    if m:
        url = m.group(1)
        check("the built address is an https URL",
              url.startswith("https://"), url)
        # The whole point: the address must actually answer. On a CI
        # runner there is no tunnel, so the address is empty - the source
        # checks above are the ones that matter there.
        if not url:
            print("  --   no live address on this machine; "
                  "skipping the fetch check")
        else:
            import urllib.error
            import urllib.request
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0",
                              "Accept": "text/html"})
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    body = r.read(4000).decode("utf-8", "replace")
                check("the address answers with the live site",
                      "Serveo - Warning" not in body and "MakGeography" in body,
                      body[:120])
            except urllib.error.URLError as e:
                check("the address answers with the live site", False, str(e))
            except Exception as e:  # noqa: BLE001
                check("the address answers with the live site", False, str(e))

print()
if failures:
    print(f"{len(failures)} of {checks} checks FAILED")
    sys.exit(1)
print(f"ALL {checks} CHECKS PASSED")
