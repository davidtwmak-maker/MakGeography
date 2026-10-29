"""Test the front end's JSON reading.

The Ask panel showed "Could not reach the assistant: The string did not
match the expected pattern." when the public tunnel returned something
that was not JSON. In Safari, `response.json()` on a non-JSON body
throws exactly that message, which says nothing about the real problem.

readJSON() reads the body as text first and raises a message that names
the actual failure: an empty response, an HTML page, or an unreadable
reply.

This test runs the real helper from static/app.js in JavaScriptCore,
because the behaviour is a browser one - a Python re-implementation would
test the wrong thing.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_JS = ROOT / "static" / "app.js"

# The helper is JavaScript, so the test runs it in a JavaScript engine.
# Node comes first because it is present on the CI runner; JavaScriptCore
# is the engine Safari uses, which is the one that produced the error.
NODE = shutil.which("node")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

if NODE:
    ENGINE = [NODE]
elif os.path.exists(JSC):
    ENGINE = [JSC]
else:
    raise SystemExit("No JavaScript engine found (node or jsc).")

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


def extract_helper() -> str:
    """The readJSON helper, exactly as the browser runs it."""
    src = APP_JS.read_text(encoding="utf-8")
    start = src.index("  async function readJSON(")
    end = src.index("\n  function addUser(", start)
    return src[start:end]


def run_js(body: str) -> str:
    """Run a JS snippet with the helper in scope; return its stdout."""
    # `print` is JSC's; Node uses console.log. The shim covers both.
    harness = (
        "if (typeof print === 'undefined') { var print = function(s) "
        "{ console.log(s); }; }\n"
        + extract_helper() + "\n" + body
    )
    tmp = pathlib.Path("/tmp/makgeo_frontend_json_test.js")
    tmp.write_text(harness, encoding="utf-8")
    proc = subprocess.run(ENGINE + [str(tmp)], capture_output=True,
                          text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:500])
    return proc.stdout


print("1. The helper exists and the front end uses it")
src = APP_JS.read_text(encoding="utf-8")
check("readJSON is defined", "async function readJSON(" in src)
check("the Ask panel uses readJSON", "await readJSON(r, \"the assistant\")" in src)
check("the essay generator uses readJSON",
      "await readJSON(r, \"the essay generator\")" in src)
check("no unguarded r.json() left", "await r.json()" not in src,
      "- found: " + " ".join(
          l.strip() for l in src.splitlines() if "await r.json()" in l))

print()
print("2. A JSON body still parses")
out = run_js("""
function fakeResponse(body, status) {
  return { status: status || 200, text: function() { return Promise.resolve(body); } };
}
(async function(){
  var d = await readJSON(fakeResponse(JSON.stringify({answer: "hi", sources: []})), "the assistant");
  print("answer=" + d.answer);
  try { await readJSON(fakeResponse("", 502), "the assistant"); print("EMPTY:no throw"); }
  catch (e) { print("EMPTY:" + e.message); }
  try { await readJSON(fakeResponse("<!DOCTYPE html><html>x</html>", 502), "the assistant"); print("HTML:no throw"); }
  catch (e) { print("HTML:" + e.message); }
  try { await readJSON(fakeResponse("502 Bad Gateway", 502), "the assistant"); print("PLAIN:no throw"); }
  catch (e) { print("PLAIN:" + e.message); }
})();
""")
print(out.rstrip())
check("a JSON body still parses", "answer=hi" in out)
check("an empty body names the status",
      "EMPTY:" in out and "empty response" in out)
check("an HTML body says it was a web page",
      "HTML:" in out and "web page" in out)
check("an unreadable body quotes it", "PLAIN:" in out and "unreadable" in out)
check("no error mentions the old Safari wording",
      "did not match the expected pattern" not in out)
check("each error names HTTP 502", out.count("502") >= 3)

print()
print("3. The message says what to do")
out2 = run_js("""
function fakeResponse(body, status) {
  return { status: status || 200, text: function() { return Promise.resolve(body); } };
}
(async function(){
  try { await readJSON(fakeResponse(""), "the assistant"); }
  catch (e) { print("EMPTYMSG:" + e.message); }
})();
""")
check("the empty-body message suggests retrying",
      "try again" in out2.lower())

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

print(f"ALL {checks} CHECKS PASSED")
