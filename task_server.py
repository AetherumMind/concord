from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, sqlite3, subprocess, time, os, zipfile

ROOT=Path.home()/"concord"
WS=ROOT/"workspace"
LEDGER=ROOT/"ledger"
AGENTS=ROOT/"agents"
DB=ROOT/"concord_tasks.db"
for p in [WS,LEDGER,AGENTS,ROOT/"uploads",ROOT/"app",ROOT/"icons"]: p.mkdir(exist_ok=True)

DEFAULT={
"architect":"Architecture, structure, feasibility.",
"scientist":"Evidence, verification, tests.",
"engineer":"Execution, implementation, repair.",
"historian":"Continuity, memory, precedent.",
"ethicist":"Safety, boundaries, consequences.",
"skeptic":"Risks, contradictions, failure modes."
}

def init():
    for k,v in DEFAULT.items():
        f=AGENTS/f"{k}.json"
        if not f.exists(): f.write_text(json.dumps({"id":k,"role":v,"weight":0.8},indent=2))
    c=sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,ts INTEGER,kind TEXT,input TEXT,output TEXT)")
    c.commit(); c.close()

def log(k,i,o):
    c=sqlite3.connect(DB)
    c.execute("INSERT INTO ledger(ts,kind,input,output) VALUES(?,?,?,?)",(int(time.time()),k,i,(o or "")[:9000]))
    c.commit(); c.close()

def safe(name):
    p=(WS/name.strip().lstrip("/")).resolve()
    if not str(p).startswith(str(WS.resolve())): raise Exception("Blocked outside workspace")
    return p

def run(cmd):
    allowed={
    "status":"pwd; ls -lh; find workspace ledger agents -maxdepth 2 -type f | sort | head -120",
    "tests":"python -m pytest -q 2>/dev/null || echo 'No tests found.'",
    "git":"git status 2>&1 || echo 'Not a git repo.'"}
    if cmd not in allowed: return "Blocked."
    r=subprocess.run(["bash","-lc",allowed[cmd]],cwd=ROOT,text=True,capture_output=True,timeout=30)
    return (r.stdout+r.stderr)[:12000]

def agents():
    init(); out=[]
    for f in sorted(AGENTS.glob("*.json")):
        try: out.append(json.loads(f.read_text()))
        except: pass
    return out

def council(text):
    votes=[]
    for a in agents():
        aid=a["id"]; vote="approve" if aid!="skeptic" else "caution"
        votes.append({"agent":aid,"vote":vote,"confidence":a.get("weight",.8),"reason":f"{aid.title()} evaluates: {text[:120]}"})
    result={"verdict":"APPROVE","votes":votes,"summary":"Proceed through safe local actions and record everything in ledger."}
    out=json.dumps(result,indent=2); log("council",text,out); return out

def task(kind,text):
    if kind=="council": out=council(text)
    elif kind=="plan": out="PLAN\n1. Define goal\n2. Ask council\n3. Create/update workspace files\n4. Run checks\n5. Save ledger receipt\n\n"+text
    elif kind in ["status","tests","git"]: out=run(kind)
    elif kind=="list_files": out="\n".join(str(p.relative_to(WS)) for p in WS.rglob("*") if p.is_file()) or "Workspace empty."
    elif kind=="read_file":
        p=safe(text); out=p.read_text(errors="replace") if p.exists() else "File not found."
    elif kind=="write_file":
        name,body=text.split("\n",1); p=safe(name); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body); out=f"Wrote workspace/{p.relative_to(WS)}"
    elif kind=="delete_file":
        p=safe(text); p.unlink() if p.exists() else None; out=f"Deleted {p.name}"
    elif kind=="note":
        f=LEDGER/"notes.md"; f.write_text((f.read_text() if f.exists() else "")+f"\n\n## {time.ctime()}\n{text}\n"); out="Note saved."
    elif kind=="todo":
        f=LEDGER/"todo.md"; f.write_text((f.read_text() if f.exists() else "")+"\n".join("- [ ] "+x for x in text.splitlines() if x.strip())+"\n"); out="Todo saved."
    elif kind=="ledger":
        c=sqlite3.connect(DB); rows=c.execute("SELECT id,ts,kind,input,output FROM ledger ORDER BY id DESC LIMIT 30").fetchall(); c.close()
        out="\n\n".join(f"#{i} {time.ctime(ts)} [{k}]\nIN: {inp[:120]}\nOUT: {o[:600]}" for i,ts,k,inp,o in rows) or "Ledger empty."
    elif kind=="export":
        z=ROOT/"concord_export.zip"
        with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as zp:
            for base in [WS,LEDGER,AGENTS]:
                for p in base.rglob("*"):
                    if p.is_file(): zp.write(p,p.relative_to(ROOT))
            for n in ["concord_app.html","task_server.py","concord_tasks.db"]:
                p=ROOT/n
                if p.exists(): zp.write(p,n)
        out=str(z)
    else: out="Unknown task."
    log(kind,text,out); return out

class H(SimpleHTTPRequestHandler):
    def sendj(self,d):
        b=json.dumps(d).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=="/api/files": self.sendj({"ok":True,"files":[str(p.relative_to(WS)) for p in WS.rglob("*") if p.is_file()]}); return
        if self.path=="/api/agents": self.sendj({"ok":True,"agents":agents()}); return
        return super().do_GET()
    def do_POST(self):
        if self.path!="/api/task": self.send_error(404); return
        n=int(self.headers.get("Content-Length",0))
        try:
            d=json.loads(self.rfile.read(n) or b"{}")
            self.sendj({"ok":True,"output":task(d.get("kind","plan"),d.get("text",""))})
        except Exception as e:
            self.sendj({"ok":False,"output":str(e)})

if __name__=="__main__":
    os.chdir(ROOT); init()
    print("CONCORD APP RUNNING: http://localhost:8080/concord_app.html")
    ThreadingHTTPServer(("127.0.0.1",8080),H).serve_forever()
