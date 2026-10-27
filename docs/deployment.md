# Deployment

## Local (development)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export MAKGEO_PASSWORD='your-password'
export MINIMAX_API_KEY='your-key'
uvicorn app.main:app --host 127.0.0.1 --port 8781
```

## As a background service (this Mac)

```bash
export MAKGEO_PASSWORD='your-password'
export MINIMAX_API_KEY='your-key'
export MAKGEO_PYTHON="$(command -v python3)"
./scripts/install_launchd.sh
```

Logs: `~/.hermes/logs/makgeo.out.log` and `~/.hermes/logs/makgeo.err.log`.

## On the public internet

The app binds to `127.0.0.1` only. Put a tunnel in front of it.

### The built-in tunnel

```bash
./scripts/install_tunnel.sh
```

This installs `com.makgeo.tunnel`, an SSH reverse tunnel that keeps the site
public. It tries serveo.net first and falls back to localtunnel when serveo
rate-limits a restart.

**The URL changes every time the tunnel restarts.** The current one is written
to:

```bash
cat ~/.hermes/logs/makgeo-url.txt
```

Send students that URL, not a saved copy of an old one. The tunnel job
rewrites the file whenever it reconnects.

Two things a visitor sees before the site:

- **serveo** shows a "Continue to Site" button — a standard interstitial, and
  it works over HTTPS.
- **localtunnel** shows a page asking for the visitor's public IP. That is
  awkward in a classroom. Prefer serveo, or a named Cloudflare tunnel.

### Named tunnel (permanent)

A quick tunnel's URL changing is fine for a demo, not for a site students use
daily. For a permanent address, use Cloudflare:

```bash
cloudflared tunnel login
cloudflared tunnel create makgeo
cloudflared tunnel route dns makgeo geo.your-domain.hk
```

Then point the tunnel at the app with a `config.yml`:

```yaml
tunnel: <TUNNEL-ID>
credentials-file: ~/.cloudflared/<TUNNEL-ID>.json
ingress:
  - hostname: geo.your-domain.hk
    service: http://127.0.0.1:8781
  - service: http_status:404
```

Run it as a service:

```bash
sudo cloudflared service install
```

Then remove the SSH tunnel so they do not fight over the port:

```bash
launchctl bootout gui/$(id -u)/com.makgeo.tunnel
```

### Security

The site has one shared password and nothing else. On a public URL:

- use a long password — the password is the only barrier;
- the session cookie is `HttpOnly` + `SameSite=Lax` but **not** `Secure`,
  because a quick tunnel can be HTTP. Set `secure=True` in `app/main.py`
  when you terminate TLS;
- the rate limit (12 questions per minute per session) protects the API key
  from a runaway, not from a determined attacker;
- consider putting Cloudflare Access in front for a second layer.

## Scheduled jobs

```bash
# Refresh the news feed — hourly is plenty
crontab -e
```

```
17 * * * * cd /path/to/MakGeography && /path/to/python3 scripts/collect_news.py >> ~/.hermes/logs/makgeo-news.log 2>&1
```

Rebuilding the knowledge base and the MC bank is manual — they need the
vault, and the MC bank needs an LLM pass.

## Troubleshooting

### The service will not start: `Form data requires "python-multipart"`

`python-multipart` is needed because the login is a form POST. A service
started before that package was installed will fail on every restart with a
uvicorn traceback, and the site will simply be down.

The service runner now imports the app **before** starting uvicorn. If the
import fails it installs any missing known dependency and retries; if the
import still fails it logs the real traceback and exits rather than serving
a dead port. To repair by hand:

```bash
"$(ls -d ~/.hermes/tools/python-*/bin/python3 | head -1)" -m pip install -q \
  fastapi uvicorn jinja2 python-multipart
```

### Checking what is actually running

The app binds to `127.0.0.1:8781`. If something else is on that port, the
launchd job will fail to start even though the code is fine.

```bash
lsof -nP -iTCP:8781 -sTCP:LISTEN     # who holds the port
launchctl list | grep makgeo         # the three jobs
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8781/
```

There should be exactly one uvicorn process, started from the repository
working directory, not from a scratch copy:

```bash
ps aux | grep '[u]vicorn' | awk '{print $2, $13}'
lsof -a -p <pid> -d cwd | tail -1     # should be ~/MakGeography
```

### A launchd job that changed but did not take effect

Editing a plist on disk does **not** change the job launchd has already
loaded. `launchctl print gui/$(id -u)/<label>` shows the environment the job
is actually running with, which is the only thing that matters:

```bash
launchctl print gui/$(id -u)/com.makgeo.news | grep -A4 'environment = '
```

If that disagrees with the plist on disk, the job has to be re-bootstrapped:

```bash
launchctl bootout gui/$(id -u)/com.makgeo.news
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.makgeo.news.plist
```

This bit once: the news job kept the path of a temporary repository copy
from the first day of setup, and the feed silently stopped updating while
the site kept serving the last good `news.json`. The plist on disk had been
corrected, but the loaded copy had not.

**A scheduled job that fails quietly is worse than one that fails loudly.**
The refresh script leaves the previous `news.json` in place on failure, so
the site keeps working - and the staleness is invisible. Check the exit code:

```bash
launchctl print gui/$(id -u)/com.makgeo.news | grep 'last exit code'
```

### Stale copies

Work was originally done in a scratch directory before the repository
existed. A copy left there can be started by mistake and will serve an
**older** knowledge base and MC bank than the live site, without any obvious
symptom. The live copy is always the one under `~/MakGeography`; the
`~/.hermes/scripts/makgeo_app_run.sh` runner points at it explicitly.
