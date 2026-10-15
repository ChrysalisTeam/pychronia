#!/usr/bin/env bash
# LOCAL-ONLY helper (do not commit) for the Django/django-cms upgrade ladder.
# Starts run_local_cms.py, probes homepage/blog/blog-post/admin, prints result, stops server.
set -u
cd "$(dirname "$0")"
PY=.venv/Scripts/python.exe

echo "=== Django/cms versions ==="
$PY -c "import django; print('Django', django.get_version())"
$PY -c "import cms; print('django-cms', cms.__version__)" 2>&1

echo "=== migrate ==="
$PY run_local_cms.py migrate 2>&1 | tail -40
MIGRATE_RC=$?

echo "=== runserver ==="
"$PY" run_local_cms.py runserver 127.0.0.1:8000 > /tmp/cmsrun/server.log 2>&1 &
SERVER_PID=$!
sleep 8

urls=(
  /fr/cms/ /en/cms/ /fr/cms/blog/ /admin/login/
  /fr/cms/contacts/                         # RstPlugin
  /fr/cms/medias/                           # JPlayerPlugin + SimpleGalleryPlugin
  /fr/cms/a-propos/historique-du-projet/    # SimpleGalleryPlugin, FilerImagePlugin
)
# first blog post URL, if any
BLOGPOST=$(curl -s --max-time 30 http://127.0.0.1:8000/fr/cms/blog/ | grep -oE 'href="/fr/cms/blog/[0-9]{4}/[^"#]+' | head -1 | sed 's/href="//')
[ -n "$BLOGPOST" ] && urls+=("$BLOGPOST")

FAIL=0
for u in "${urls[@]}"; do
  code=$(curl -s -o /tmp/cmsrun/last.html -w "%{http_code}" --max-time 30 "http://127.0.0.1:8000$u")
  printf "%-50s %s\n" "$u" "$code"
  if [ "$code" != "200" ] && [ "$code" != "302" ]; then FAIL=1; fi
done

kill $SERVER_PID 2>/dev/null
sleep 1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%run_local_cms.py runserver%'\" | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1

echo "=== server log tail ==="
tail -n 25 /tmp/cmsrun/server.log

if [ "$FAIL" = "1" ]; then
  echo "RESULT: FAIL"
  exit 1
else
  echo "RESULT: OK"
fi
