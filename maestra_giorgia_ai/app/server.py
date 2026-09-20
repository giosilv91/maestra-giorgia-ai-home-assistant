import json, os, sqlite3, threading, urllib.request, urllib.error
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DATA=Path('/data'); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'maestra_giorgia_ai.db'; SETTINGS=DATA/'settings.json'
INDEX=Path(__file__).with_name('index.html'); PORT=8099
PROMPT="""Sei Maestra, assistente AI professionale di Giorgia Mauro per il sostegno nella scuola primaria italiana.
Rispondi in italiano, in modo pratico, inclusivo e rispettoso. Non inventare voti, diagnosi o progressi.
Quando crei materiali indica obiettivo, consegna, facilitazioni e soluzione per la docente."""

class Store:
    def __init__(self):
        self.lock=threading.Lock()
        self.db=sqlite3.connect(DB,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        with self.lock:
            self.db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,class_name TEXT,strengths TEXT,difficulties TEXT,strategies TEXT,goals TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS evaluations(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER NOT NULL,eval_date TEXT,term INTEGER,subject TEXT,activity TEXT,grade TEXT,autonomy INTEGER,notes TEXT,FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER NOT NULL,area TEXT,description TEXT,status TEXT,notes TEXT,updated_at TEXT,FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS diary(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER NOT NULL,diary_date TEXT,category TEXT,text TEXT,participation INTEGER,support_level INTEGER,FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS materials(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER,kind TEXT,title TEXT,content TEXT,created_at TEXT);
            """)
            self.db.commit()
    def all(self,sql,args=()):
        with self.lock:return [dict(x) for x in self.db.execute(sql,args).fetchall()]
    def one(self,sql,args=()):
        with self.lock:
            r=self.db.execute(sql,args).fetchone(); return dict(r) if r else None
    def write(self,sql,args=()):
        with self.lock:
            c=self.db.execute(sql,args); self.db.commit(); return c.lastrowid
    def context(self,sid):
        if not sid:return ''
        s=self.one('SELECT * FROM students WHERE id=?',(sid,))
        if not s:return ''
        g=self.all('SELECT * FROM goals WHERE student_id=? ORDER BY id DESC LIMIT 20',(sid,))
        e=self.all('SELECT * FROM evaluations WHERE student_id=? ORDER BY eval_date DESC,id DESC LIMIT 12',(sid,))
        d=self.all('SELECT * FROM diary WHERE student_id=? ORDER BY diary_date DESC,id DESC LIMIT 10',(sid,))
        parts=[f"ALUNNO: {s['name']} | {s.get('class_name','')}",f"Punti di forza: {s.get('strengths','')}",f"Difficoltà: {s.get('difficulties','')}",f"Strategie: {s.get('strategies','')}",f"Obiettivi generali: {s.get('goals','')}","OBIETTIVI:"]
        parts += [f"- {x.get('area','')}: {x.get('description','')} [{x.get('status','')}]" for x in g]
        parts += ["VALUTAZIONI:"]+[f"- {x.get('eval_date','')} {x.get('subject','')}: {x.get('grade','')} | autonomia {x.get('autonomy','')}/5" for x in e]
        parts += ["DIARIO:"]+[f"- {x.get('diary_date','')}: {x.get('text','')}" for x in d]
        return "\n".join(parts)
store=Store()

def load_settings():
    try:return json.loads(SETTINGS.read_text())
    except:return {'teacher_name':'Giorgia Mauro','assistant_name':'Maestra','gemini_model':'gemini-3.8-flash','gemini_api_key':''}
def save_settings(x):
    SETTINGS.write_text(json.dumps(x,ensure_ascii=False,indent=2)); os.chmod(SETTINGS,0o600)

def gemini(prompt,context=''):
    s=load_settings(); key=s.get('gemini_api_key','').strip()
    if not key: raise RuntimeError('Inserisci la Gemini API key nelle Impostazioni')
    model=s.get('gemini_model') or 'gemini-3.8-flash'
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    body={'contents':[{'parts':[{'text':PROMPT+'\n\n'+context+'\n\nRICHIESTA:\n'+prompt}]}]}
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as r: out=json.loads(r.read().decode())
    try:return ''.join(p.get('text','') for p in out['candidates'][0]['content']['parts']).strip()
    except: raise RuntimeError(out.get('error',{}).get('message','Risposta Gemini non valida'))

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def route_path(self): return urlparse(self.path).path
    def json(self):
        n=int(self.headers.get('Content-Length','0')); raw=self.rfile.read(n) if n else b'{}'
        return json.loads(raw.decode() or '{}')
    def sendj(self,obj,code=200):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def html(self):
        raw=INDEX.read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        try:
            p=self.route_path()
            if p=='/' or not p.startswith('/api/'): return self.html()
            q=parse_qs(urlparse(self.path).query); sid=q.get('student_id',[None])[0]
            if p=='/api/status':
                s=load_settings(); s['gemini_api_key']=bool(s.get('gemini_api_key')); return self.sendj({'ok':True,'settings':s})
            if p=='/api/students': return self.sendj({'ok':True,'items':store.all('SELECT * FROM students ORDER BY name')})
            if p=='/api/evaluations': return self.sendj({'ok':True,'items':store.all('SELECT * FROM evaluations WHERE student_id=? ORDER BY eval_date DESC,id DESC',(sid,)) if sid else []})
            if p=='/api/goals': return self.sendj({'ok':True,'items':store.all('SELECT * FROM goals WHERE student_id=? ORDER BY id DESC',(sid,)) if sid else []})
            if p=='/api/diary': return self.sendj({'ok':True,'items':store.all('SELECT * FROM diary WHERE student_id=? ORDER BY diary_date DESC,id DESC',(sid,)) if sid else []})
            if p=='/api/materials': return self.sendj({'ok':True,'items':store.all('SELECT * FROM materials ORDER BY id DESC LIMIT 100')})
            return self.sendj({'ok':False,'error':'Endpoint non trovato'},404)
        except Exception as e:return self.sendj({'ok':False,'error':str(e)},500)
    def do_POST(self):
        try:
            p=self.route_path(); b=self.json(); now=datetime.now().isoformat(timespec='seconds')
            if p=='/api/students':
                if b.get('id'):
                    store.write('UPDATE students SET name=?,class_name=?,strengths=?,difficulties=?,strategies=?,goals=? WHERE id=?',(b.get('name',''),b.get('class_name',''),b.get('strengths',''),b.get('difficulties',''),b.get('strategies',''),b.get('goals',''),b['id'])); i=b['id']
                else:i=store.write('INSERT INTO students(name,class_name,strengths,difficulties,strategies,goals,created_at) VALUES(?,?,?,?,?,?,?)',(b.get('name',''),b.get('class_name',''),b.get('strengths',''),b.get('difficulties',''),b.get('strategies',''),b.get('goals',''),now))
                return self.sendj({'ok':True,'id':i})
            if p=='/api/evaluations':
                i=store.write('INSERT INTO evaluations(student_id,eval_date,term,subject,activity,grade,autonomy,notes) VALUES(?,?,?,?,?,?,?,?)',(b.get('student_id'),b.get('eval_date') or date.today().isoformat(),int(b.get('term') or 1),b.get('subject',''),b.get('activity',''),b.get('grade',''),int(b.get('autonomy') or 3),b.get('notes','')))
                return self.sendj({'ok':True,'id':i})
            if p=='/api/goals':
                i=store.write('INSERT INTO goals(student_id,area,description,status,notes,updated_at) VALUES(?,?,?,?,?,?)',(b.get('student_id'),b.get('area',''),b.get('description',''),b.get('status','Da iniziare'),b.get('notes',''),now)); return self.sendj({'ok':True,'id':i})
            if p=='/api/diary':
                i=store.write('INSERT INTO diary(student_id,diary_date,category,text,participation,support_level) VALUES(?,?,?,?,?,?)',(b.get('student_id'),b.get('diary_date') or date.today().isoformat(),b.get('category','Apprendimento'),b.get('text',''),int(b.get('participation') or 3),int(b.get('support_level') or 3))); return self.sendj({'ok':True,'id':i})
            if p=='/api/ai':
                txt=gemini(b.get('prompt',''),store.context(b.get('student_id'))); return self.sendj({'ok':True,'text':txt})
            if p=='/api/materials':
                i=store.write('INSERT INTO materials(student_id,kind,title,content,created_at) VALUES(?,?,?,?,?)',(b.get('student_id'),b.get('kind','Materiale'),b.get('title','Materiale'),b.get('content',''),now)); return self.sendj({'ok':True,'id':i})
            if p=='/api/settings':
                s=load_settings()
                for k in ('teacher_name','assistant_name','gemini_model'):
                    if k in b:s[k]=b[k]
                if b.get('gemini_api_key'):s['gemini_api_key']=b['gemini_api_key'].strip()
                if b.get('remove_gemini_key'):s['gemini_api_key']=''
                save_settings(s); return self.sendj({'ok':True})
            if p=='/api/test_ai':
                return self.sendj({'ok':True,'text':gemini('Rispondi soltanto con: Maestra collegata correttamente.')})
            return self.sendj({'ok':False,'error':'Endpoint non trovato'},404)
        except urllib.error.HTTPError as e:
            try:d=e.read().decode()
            except:d=str(e)
            return self.sendj({'ok':False,'error':d},502)
        except Exception as e:return self.sendj({'ok':False,'error':str(e)},400)
    def do_DELETE(self):
        try:
            a=self.route_path().strip('/').split('/')
            mp={'students':'students','evaluations':'evaluations','goals':'goals','diary':'diary','materials':'materials'}
            if len(a)!=3 or a[1] not in mp:return self.sendj({'ok':False,'error':'Risorsa non valida'},404)
            store.write(f'DELETE FROM {mp[a[1]]} WHERE id=?',(int(a[2]),)); return self.sendj({'ok':True})
        except Exception as e:return self.sendj({'ok':False,'error':str(e)},400)

if __name__=='__main__':
    print(f'Maestra Giorgia AI su 0.0.0.0:{PORT}',flush=True)
    ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
