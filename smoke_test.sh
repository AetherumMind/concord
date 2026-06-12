#!/data/data/com.termux/files/usr/bin/bash
set -e
cd ~/concord
python -m py_compile task_server.py
pkill -f task_server.py 2>/dev/null || true
python task_server.py >$HOME/concord/concord.log 2>&1 &
sleep 2

curl -s -X POST http://127.0.0.1:8080/api/task \
-H "Content-Type: application/json" \
-d '{"kind":"status","text":"health"}' | grep '"ok": true'

curl -s -X POST http://127.0.0.1:8080/api/task \
-H "Content-Type: application/json" \
-d '{"kind":"write_file","text":"release_check.md\n# Concord Release Check\n\nWorkspace write passed."}' | grep '"ok": true'

curl -s -X POST http://127.0.0.1:8080/api/task \
-H "Content-Type: application/json" \
-d '{"kind":"read_file","text":"release_check.md"}' | grep 'Workspace write passed'

echo "CONCORD RELEASE CHECK PASSED"
