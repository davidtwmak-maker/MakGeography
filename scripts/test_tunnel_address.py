"""Test the address a student is given.

Serveo shows a warning page to real browsers on an HTTP tunnel. The page
is served by Serveo's edge, before the request reaches the app, so the
app cannot redirect around it - every path, including the fetch() the
Ask panel makes, gets the same HTML.

Serveo does skip the page for a request that carries
"serveo-skip-browser-warning", and answers that with a 302 that sets the
cookie for a year. So the address handed to a student carries the
parameter, and their first visit sets the cookie and lands on the real
site.

This checks that:
  - the URL file carries the parameter
  - the tunnel script that writes it also writes the parameter
  - the address actually serves the site, not the warning page
"""

import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

HOME = pathlib.Path.home()
URL_FILE = HOME / ".hermes" / "logs" / "makgeo-url.txt"
CF_FILE = HOME / ".hermes" / "logs" / "makgeo-url-cf.txt"
RUNNER = HOME / ".hermes" / "scripts" / "makgeo_tunnel_run.sh"
REPO_RUNNER = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "install_tunnel.sh"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.4 Safari/605.1.15")

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


def fetch(url, cookie_jar=None):
    """A browser-like GET. Returns (status, body)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    opener = urllib.request.build_opener()
    if cookie_jar is not None:
        opener.addheaders = []
        # urllib keeps no cookie jar across requests by default, so the
        # skip URL is fetched with a jar that the second request reuses.
        import http.cookiejar
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar))
    try:
        with opener.open(req, timeout=25) as r:
            return r.status, r.read(8000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(8000).decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return 0, str(e)


print("1. The tunnel script writes the skip parameter")
for label, path in (("the installed script", RUNNER),
                     ("the repo installer", REPO_RUNNER)):
    if not path.is_file():
        print(f"  --   {label} is not here; skipped")
        continue
    text = path.read_text(encoding="utf-8")
    check(f"{label} writes ?serveo-skip-browser-warning",
          "serveo-skip-browser-warning=true" in text)

print("2. The URL file carries the skip parameter")
if not URL_FILE.is_file():
    print("  --   no URL file on this machine; skipped")
else:
    url = URL_FILE.read_text(encoding="utf-8").strip()
    check("the URL file names the skip parameter",
          "serveo-skip-browser-warning=true" in url, url)
    check("the URL file names the permanent Serveo address",
          "serveousercontent.com" in url, url)

print("3. The address actually serves the site")
if not URL_FILE.is_file():
    print("  --   no URL file on this machine; skipped")
else:
    url = URL_FILE.read_text(encoding="utf-8").strip()
    if not url.startswith("https://"):
        print("  --   the URL file holds no address; skipped")
    else:
        import http.cookiejar
        jar = http.cookiejar.CookieJar()
        status, body = fetch(url, jar)
        check("the address answers", status == 200, f"status {status}")
        check("the address serves the site, not the warning page",
              "Serveo - Warning" not in body and "MakGeography" in body,
              body[:120])

        # And the second visit, with the cookie now set, is clean too.
        status2, body2 = fetch(url.split("?")[0], jar)
        check("the second visit is clean as well",
              status2 == 200 and "Serveo - Warning" not in body2,
              f"status {status2}")

print("4. The Cloudflare tunnel needs no parameter")
if not CF_FILE.is_file():
    print("  --   no Cloudflare URL file on this machine; skipped")
else:
    cf = CF_FILE.read_text(encoding="utf-8").strip()
    check("the Cloudflare address carries no skip parameter",
          "serveo-skip-browser-warning" not in cf, cf)

print()
if failures:
    print(f"{len(failures)} of {checks} checks FAILED")
    sys.exit(1)
print(f"ALL {checks} CHECKS PASSED")
