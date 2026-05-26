#!/usr/bin/env bash
# Vercel build hook — runs once during deploy (NOT at runtime).
# Installs deps + collects static files into `staticfiles/`. Vercel.json
# uses `includeFiles: "staticfiles/**"` so the bundled Lambda has them.
set -euo pipefail

export DJANGO_SETTINGS_MODULE=hotel_prj.settings

# settings.py refuses to import if SECRET_KEY is unset. During build we
# don't need the real one — collectstatic doesn't touch the DB or sessions.
# A fallback prevents the build from failing if Vercel env didn't propagate.
: "${SECRET_KEY:=build-time-placeholder-not-used-at-runtime}"
export SECRET_KEY

# Same idea: ALLOWED_HOSTS gets validated during settings import in non-DEBUG
# mode. Build-time only — runtime uses the real env var.
: "${ALLOWED_HOSTS:=*}"
export ALLOWED_HOSTS

echo "::group::Installing dependencies"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
echo "::endgroup::"

echo "::group::Collecting static files"
python3 manage.py collectstatic --noinput --clear
echo "::endgroup::"

# Quick sanity check — if this list is empty, the next deploy will 500.
echo "::group::Verifying staticfiles/ contains output"
if [ -z "$(ls -A staticfiles 2>/dev/null || true)" ]; then
  echo "ERROR: staticfiles/ is empty — collectstatic produced no output." >&2
  exit 1
fi
ls staticfiles | head -20
echo "::endgroup::"

echo "Build completed successfully"
