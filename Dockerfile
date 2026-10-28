# MakGeography — the running site.
#
# The site is a FastAPI app. GitHub Pages cannot run it, so it is
# deployed to a container host (Render, Fly, Railway, any of them) from
# this repository. The static GitHub Pages copy is a separate thing and
# does not use this image.
#
# The data directory is copied in, because the MC drilling needs the
# official HKEAA question images and the map extracts. It is about
# 200 MB, which is fine for a container image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a change to the data does not rebuild them.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The application.
COPY app/ ./app/
COPY static/ ./static/
COPY templates/ ./templates/
COPY data/ ./data/

# The HKEAA briefing decks in data/papers are 55 MB of source material
# for building the question images. The site does not read them, so they
# are removed from the image.
RUN rm -rf /app/data/papers

# The roster and the activity log are NOT in the repository - they hold
# the students' names. On a deployed server they are set with
# MAKGEO_ROSTER_PATH (a file) or MAKGEO_ROSTER_JSON (inline), and the
# activity log is written to MAKGEO_ACTIVITY_LOG.
RUN mkdir -p /app/data

# Render uses port 10000 by default; the service must bind 0.0.0.0 to
# be reachable from outside the container.
EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
