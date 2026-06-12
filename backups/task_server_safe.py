from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, sqlite3, subprocess, time, os, zipfile

ROOT=Path.home()/"concord"
WS=ROOT/"workspace"
LEDGER=ROOT/"ledger"
AGENTS=ROOT/"agents"
UPLOADS=ROOT/"uploads"
APP=ROOT/"app"
DB=ROOT/"concord_tasks.db"

for p in [WS,LEDGER,AGENTS,UPLOADS,APP]:
    p.mkdir(parents=True,exist_ok=True)

DEFAULT_AGENTS={
"architect":{"role":"Structure, feasibility, architecture.","weight":0.84},
"scientist":{"role":"Evidence, tests, verification.","weight":0.88},
"historian":{"role":"Continuity, precedent, memory.","weight":0.76},
"ethicist":{"role":"Risk, safety, boundaries.","weight":0.86},
"skeptic":{"role":"Failure modes and contradictions.","weight":0.82},
"engineer":{"role":"Implementation and execution.","weight":0.90}
}

def init_agents():
    for k,v in DEFAULT_AGENTS.items():
        f=AGENTS/f"{k}.json"
        if not f.exists():
            f.write_text(json.dumps({"id":k,**v},indent=2))

def db():
    c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER,
        kind TEXT,
        title TEXT,
        input TEXT,
        output TEXT
    )""")
    c.commit()
    return c

def log(kind,title,inp,out):
    c=db()
    c.execute("INSERT INTO ledger(ts,kind,title,input,output) VALUES(?,?,?,?,?)",
              (int(time.time()),kind,title,inp or "",(out or "")[:12000]))
    c.commit()
    c.close()

def j(ok=True,output="",extra=None):
    d={"ok":ok,"output":output}
    if extra: d.update(extra)
    return json.dumps(d).encode()

def safe_path(raw):
    raw=(raw or "").strip().lstrip("/")
    p=(WS/raw).resolve()
    if not str(p).startswith(str(WS.resolve())):
        raise Exception("Blocked path outside workspace")
    return p

def run_allowed(name):
    cmds={
      "status":"pwd; ls -lh; echo; find workspace ledger agents uploads app -maxdepth 2 -type f | sort | head -160",
      "tests":"python -m pytest -q 2>/dev/null || echo 'No pytest tests found.'",
      "git":"git status 2>&1 || echo 'Not a git repository.'",
      "tree":"find . -maxdepth 3 -type f | sort | head -220"
    }
    if name not in cmds: return "Blocked command."
    r=subprocess.run(["bash","-lc",cmds[name]],cwd=ROOT,text=True,capture_output=True,timeout=35)
    return (r.stdout+r.stderr).strip()[:16000]

def files():
    out=[]
    for p in WS.rglob("*"):
        if p.is_file():
            out.append({"path":str(p.relative_to(WS)),"size":p.stat().st_size,"modified":int(p.stat().st_mtime)})
    return out

def ledger(limit=80):
    c=db()
    rows=c.execute("SELECT id,ts,kind,title,input,output FROM ledger ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    c.close()
    return [{"id":i,"ts":ts,"kind":k,"title":t,"input":inp,"output":out} for i,ts,k,t,inp,out in rows]

def load_agents():
    init_agents()
    arr=[]
    for f in sorted(AGENTS.glob("*.json")):
        try: arr.append(json.loads(f.read_text()))
        except Exception: pass
    return arr

def council(text):
    text=text.strip()
    arr=load_agents()
    votes=[]
    for a in arr:
        aid=a.get("id","agent")
        role=a.get("role","")
        weight=float(a.get("weight",0.75))
        vote="approve"
        if aid=="skeptic": vote="caution"
        confidence=round(min(.96,max(.45,weight)),2)
        reason=f"{aid.title()} examines '{text[:120]}' through {role}"
        if aid=="engineer": reason="Engineer recommends converting the goal into safe file, ledger, and test actions."
        if aid=="ethicist": reason="Ethicist approves only bounded local actions inside Concord workspace."
        if aid=="skeptic": reason="Skeptic flags risk: vague goals, silent failures, and unsafe command expansion."
        votes.append({"agent":aid,"role":role,"vote":vote,"confidence":confidence,"reason":reason})
    approvals=sum(1 for v in votes if v["vote"]=="approve")
    avg=round(sum(v["confidence"] for v in votes)/max(1,len(votes)),2)
    verdict="APPROVE" if approvals>=4 else "HOLD"
    result={"verdict":verdict,"confidence":avg,"approvals":approvals,"total":len(votes),"votes":votes}
    out=json.dumps(result,indent=2)
    log("council","Council deliberation",text,out)
    return result

def task(kind,text):
    if kind=="plan":
        out=f"PLAN\n1. Define outcome\n2. Inspect workspace\n3. Ask council\n4. Execute safe local action\n5. Record ledger receipt\n6. Review result\n\nINPUT:\n{text}"
    elif kind=="council":
        return json.dumps(council(text),indent=2)
    elif kind in ["status","tests","git","tree"]:
        out=run_allowed(kind)
    elif kind=="list_files":
        out="\n".join(x["path"] for x in files()) or "Workspace empty."
    elif kind=="read_file":
        p=safe_path(text); out=p.read_text(errors="replace")[:20000] if p.exists() else "File not found."
    elif kind=="write_file":
        first,body=text.split("\n",1)
        p=safe_path(first); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body)
        out=f"Wrote workspace/{p.relative_to(WS)}"
    elif kind=="delete_file":
        p=safe_path(text); 
        if p.exists(): p.unlink(); out=f"Deleted workspace/{p.relative_to(WS)}"
        else: out="File not found."
    elif kind=="save_note":
        f=LEDGER/"notes.md"
        old=f.read_text() if f.exists() else ""
        f.write_text(old+f"\n\n## {time.ctime()}\n{text}\n")
        out="Saved note to ledger/notes.md"
    elif kind=="todo":
        f=LEDGER/"todo.md"
        old=f.read_text() if f.exists() else ""
        lines=[x.strip() for x in text.splitlines() if x.strip()]
        f.write_text(old+"\n".join(f"- [ ] {x}" for x in lines)+"\n")
        out=f"Added {len(lines)} todo item(s)."
    elif kind=="ledger":
        out=json.dumps(ledger(30),indent=2)
    elif kind=="export":
        out=str(export_zip())
    else:
        out="Unknown task."
    log("task",kind,text,out)
    return out

def export_zip():
    z=ROOT/"concord_export.zip"
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as zipf:
        for base in [WS,LEDGER,AGENTS]:
            for p in base.rglob("*"):
                if p.is_file(): zipf.write(p,p.relative_to(ROOT))
        if DB.exists(): zipf.write(DB,DB.name)
        for name in ["concord_pro.html","task_server.py","manifest.json","service-worker.js"]:
            p=ROOT/name
            if p.exists(): zipf.write(p,name)
    log("export","Export package","",str(z))
    return z

class H(SimpleHTTPRequestHandler):
    def reply(self,body,status=200):
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            if self.path=="/api/files":
                self.reply(j(True,"",{"files":files()})); return
            if self.path=="/api/ledger":
                self.reply(j(True,"",{"ledger":ledger()})); return
            if self.path=="/api/agents":
                self.reply(j(True,"",{"agents":load_agents()})); return
            if self.path=="/api/export":
                self.reply(j(True,str(export_zip()))); return
            return super().do_GET()
        except Exception as e:
            self.reply(j(False,str(e)))

    def do_POST(self):
        if not self.path.startswith("/api/"):
            self.send_error(404); return
        n=int(self.headers.get("Content-Length",0))
        try: data=json.loads(self.rfile.read(n) or b"{}")
        except Exception: data={}
        try:
            if self.path=="/api/task":
                self.reply(j(True,task(data.get("kind","plan"),data.get("text","")))); return
            if self.path=="/api/council":
                self.reply(j(True,"",{"council":council(data.get("text",""))})); return
            if self.path=="/api/file":
                mode=data.get("mode","read")
                path=data.get("path","")
                p=safe_path(path)
                if mode=="read":
                    self.reply(j(True,p.read_text(errors="replace") if p.exists() else "File not found.")); return
                if mode=="write":
                    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(data.get("content",""))
                    log("file","write",path,"saved")
                    self.reply(j(True,f"Wrote workspace/{p.relative_to(WS)}")); return
                if mode=="delete":
                    if p.exists(): p.unlink()
                    log("file","delete",path,"deleted")
                    self.reply(j(True,f"Deleted workspace/{p.relative_to(WS)}")); return
            if self.path=="/api/agent":
                aid=data.get("id","agent").replace("/","").replace("..","")
                payload={"id":aid,"role":data.get("role",""),"weight":float(data.get("weight",0.75))}
                (AGENTS/f"{aid}.json").write_text(json.dumps(payload,indent=2))
                log("agent","save",aid,json.dumps(payload))
                self.reply(j(True,"Agent saved.")); return
            self.reply(j(False,"Unknown API path"),404)
        except Exception as e:
            self.reply(j(False,str(e)))

if __name__=="__main__":
    os.chdir(ROOT)
    init_agents()
    db().close()
    print("CONCORD COMPLETE running:")
    print("http://localhost:8080/concord_pro.html")
    ThreadingHTTPServer(("127.0.0.1",8080),H).serve_forever()
