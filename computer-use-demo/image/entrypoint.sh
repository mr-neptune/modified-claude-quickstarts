#!/bin/bash
set -e

./start_all.sh
./novnc_startup.sh

uvicorn computer_use_demo.api:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn_stdout.log 2>&1 &

echo "Computer Use Demo is ready!"
echo "-> API + demo UI: http://localhost:8000/static/index.html"
echo "-> noVNC browser view: http://localhost:6080/vnc.html"

# Keep the container running
tail -f /dev/null
