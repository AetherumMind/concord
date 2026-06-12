from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, subprocess, sqlite3, time, os

ROOT = Path.home() / "concord"
DB = ROOT / "concord_tasks.db"

def init_db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER,
        kind TEXT,
        input TEXT,
        output TEXT
    )""")
    con.commit()
    con.close()

def record(kind, inp, out):
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO tasks(ts,kind,input,output) VALUES(?,?,?,?)",
                (int(time.time()), kind, inp, out))
    con.commit()
    con.close()

def safe_run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=20)
    return (r.stdout + r.stderr).strip()[:8000]

def do_task(kind, text):
    if kind == "status":
        out = safe_run(["bash", "-lc", "pwd; ls -lh; git status 2>/dev/null || true"])
    elif kind == "run_tests":
        out = safe_run(["bash", "-lc", "python -m pytest -q 2>/dev/null || echo 'No pytest tests found or pytest not installed.'"])
    elif kind == "git_status":
        out = safe_run(["git", "status"])
    elif kind == "save_note":
        p = ROOT / "concord_notes.md"
        with p.open("a") as f:
            f.write(f"\n\n## {time.ctime()}\n{text}\n")
        out = f"Saved note to {p}"
    elif kind == "make_todo":
        p = ROOT / "concord_todo.md"
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        with p.open("a") as f:
            for x in lines:
                f.write(f"- [ ] {x}\n")
        out = f"Added {len(lines)} todo item(s) to {p}"
    elif kind == "read_notes":
        p = ROOT / "concord_notes.md"
        out = p.read_text()[-8000:] if p.exists() else "No notes yet."
    elif kind == "plan":
        out = "Task plan:\n1. Clarify desired outcome.\n2. Break into safe local actions.\n3. Execute allowed actions only.\n4. Record receipt in concord_tasks.db.\n\nInput:\n" + text
    else:
        out = "Unknown task."
    record(kind, text, out)
    return out

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/task":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        kind = data.get("kind", "plan")
        text = data.get("text", "")
        try:
            out = do_task(kind, text)
            body = json.dumps({"ok": True, "output": out}).encode()
        except Exception as e:
            body = json.dumps({"ok": False, "output": str(e)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    os.chdir(ROOT)
    init_db()
    print("Concord task server running at http://localhost:8080/concord.html")
    ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
