from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, subprocess, sqlite3, time, os

ROOT = Path.home() / "concord"
WORKSPACE = ROOT / "workspace"
LEDGER = ROOT / "ledger"
DB = ROOT / "concord_tasks.db"

WORKSPACE.mkdir(exist_ok=True)
LEDGER.mkdir(exist_ok=True)

def safe_path(raw):
    raw = raw.strip().lstrip("/")
    p = (WORKSPACE / raw).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError("Blocked path outside workspace")
    return p

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
                (int(time.time()), kind, inp, out[:4000]))
    con.commit()
    con.close()

def safe_run(cmd):
    allowed = {
        "status": "pwd; ls -lh; find workspace ledger app -maxdepth 2 -type f 2>/dev/null | head -80",
        "tests": "python -m pytest -q 2>/dev/null || echo 'No pytest tests found.'",
        "git": "git status 2>&1 || echo 'Not a git repo.'"
    }
    if cmd not in allowed:
        return "Command blocked."
    r = subprocess.run(["bash","-lc",allowed[cmd]], cwd=ROOT, text=True, capture_output=True, timeout=25)
    return (r.stdout + r.stderr).strip()[:10000]

def council(text):
    agents = [
        ("Architect","Build modular workspace, task, ledger, and council layers."),
        ("Scientist","Verify every action through repeatable checks and saved receipts."),
        ("Historian","Preserve backups and project memory so progress is traceable."),
        ("Ethicist","Restrict actions to ~/concord/workspace and block unsafe commands."),
        ("Skeptic","Watch for silent failures, broken UI injection, and command creep."),
        ("Synthesist","Proceed incrementally: workspace first, then ledger, then richer council.")
    ]
    out = []
    for name, reason in agents:
        out.append({"agent":name,"vote":"approve" if name!="Skeptic" else "caution","confidence":0.78,"reason":reason})
    return json.dumps(out, indent=2)

def do_task(kind, text):
    if kind == "plan":
        out = "Task plan:\n1. Clarify outcome.\n2. Break into safe local actions.\n3. Execute only allowed operations.\n4. Record result in ledger.\n\nInput:\n" + text
    elif kind == "council":
        out = council(text)
    elif kind in ("status","tests","git"):
        out = safe_run(kind)
    elif kind == "list_files":
        files = []
        for p in WORKSPACE.rglob("*"):
            if p.is_file():
                files.append(str(p.relative_to(WORKSPACE)))
        out = "\n".join(files) or "Workspace empty."
    elif kind == "read_file":
        p = safe_path(text)
        out = p.read_text(errors="replace")[:12000] if p.exists() else "File not found."
    elif kind == "write_file":
        first, body = text.split("\n",1)
        p = safe_path(first)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        out = f"Wrote workspace/{p.relative_to(WORKSPACE)}"
    elif kind == "save_note":
        p = LEDGER / "notes.md"
        with p.open("a") as f:
            f.write(f"\n\n## {time.ctime()}\n{text}\n")
        out = "Saved note to ledger/notes.md"
    elif kind == "todo":
        p = LEDGER / "todo.md"
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        with p.open("a") as f:
            for x in lines:
                f.write(f"- [ ] {x}\n")
        out = f"Added {len(lines)} todo item(s)."
    elif kind == "ledger":
        con = sqlite3.connect(DB)
        rows = con.execute("SELECT id,ts,kind,input,output FROM tasks ORDER BY id DESC LIMIT 20").fetchall()
        con.close()
        out = "\n\n".join([f"#{i} {time.ctime(ts)} [{k}]\nINPUT: {inp[:120]}\nOUTPUT: {out[:500]}" for i,ts,k,inp,out in rows]) or "Ledger empty."
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
        try:
            out = do_task(data.get("kind","plan"), data.get("text",""))
            body = json.dumps({"ok":True,"output":out}).encode()
        except Exception as e:
            body = json.dumps({"ok":False,"output":str(e)}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    os.chdir(ROOT)
    init_db()
    print("Concord workspace server running:")
    print("http://localhost:8080/concord.html")
    ThreadingHTTPServer(("127.0.0.1",8080), Handler).serve_forever()
