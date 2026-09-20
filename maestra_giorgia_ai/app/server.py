import json, os, sqlite3, threading, urllib.request, urllib.error, base64, io, wave, time
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
            cols=[r[1] for r in self.db.execute("PRAGMA table_info(evaluations)").fetchall()]
            if "eval_type" not in cols:
                self.db.execute("ALTER TABLE evaluations ADD COLUMN eval_type TEXT DEFAULT 'Orale'")
                self.db.commit()
            # Migrazione dati V1/V1.2: in passato il vero tipo prova era spesso scritto in activity.
            self.db.execute("""UPDATE evaluations
                SET eval_type='Scritta'
                WHERE lower(trim(coalesce(activity,''))) LIKE '%verifica%'
                  AND lower(trim(coalesce(eval_type,''))) IN ('','orale')""")
            self.db.execute("""UPDATE evaluations
                SET eval_type='Scritta'
                WHERE lower(trim(coalesce(activity,''))) IN ('scritto','scritta','verifica scritta')
                  AND lower(trim(coalesce(eval_type,''))) IN ('','orale')""")
            self.db.execute("""UPDATE evaluations
                SET eval_type='Orale'
                WHERE lower(trim(coalesce(activity,''))) IN ('orale','interrogazione')
                  AND lower(trim(coalesce(eval_type,'')))=''""")
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
    except:return {'teacher_name':'Giorgia Mauro','assistant_name':'Maestra','gemini_model':'gemini-3.8-flash','gemini_api_key':'','ai_provider':'auto','ha_ai_task_entity':'','tts_voice':'Kore','tts_model':'gemini-3.1-flash-tts-preview','auto_speak':True}
def save_settings(x):
    SETTINGS.write_text(json.dumps(x,ensure_ascii=False,indent=2)); os.chmod(SETTINGS,0o600)

def _http_json(url, body=None, headers=None, timeout=180):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url,data=data,headers=headers or {'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read()
        return json.loads(raw.decode()) if raw else {}

def gemini(prompt,context=''):
    s=load_settings(); key=s.get('gemini_api_key','').strip()
    if not key: raise RuntimeError('Inserisci la Gemini API key nelle Impostazioni')
    model=s.get('gemini_model') or 'gemini-3.8-flash'
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    body={'contents':[{'parts':[{'text':PROMPT+'\n\n'+context+'\n\nRICHIESTA:\n'+prompt}]}]}
    last=None
    for attempt in range(3):
        try:
            out=_http_json(url,body,{'Content-Type':'application/json'},180)
            text=''.join(p.get('text','') for p in out.get('candidates',[{}])[0].get('content',{}).get('parts',[])).strip()
            if text:return text
            raise RuntimeError(out.get('error',{}).get('message','Risposta Gemini non valida'))
        except urllib.error.HTTPError as e:
            detail=e.read().decode(errors='ignore')
            last=RuntimeError(detail or str(e))
            if e.code not in (429,500,502,503,504) or attempt==2: break
            time.sleep(1.5*(attempt+1))
        except Exception as e:
            last=e
            if attempt==2: break
            time.sleep(1.0*(attempt+1))
    raise RuntimeError(f'Gemini non disponibile: {last}')

def _ha_headers():
    token=os.environ.get('SUPERVISOR_TOKEN','').strip()
    if not token: raise RuntimeError('Token Home Assistant non disponibile')
    return {'Authorization':f'Bearer {token}','Content-Type':'application/json'}

def ha_ai_tasks():
    try:
        states=_http_json('http://supervisor/core/api/states',None,_ha_headers(),30)
        out=[]
        for st in states:
            eid=st.get('entity_id','')
            if eid.startswith('ai_task.'):
                out.append({'entity_id':eid,'name':st.get('attributes',{}).get('friendly_name') or eid,'state':st.get('state')})
        return out
    except Exception:
        return []

def _find_text(obj):
    if isinstance(obj,str): return obj.strip()
    if isinstance(obj,dict):
        if isinstance(obj.get('data'),str) and obj.get('data').strip(): return obj['data'].strip()
        if isinstance(obj.get('text'),str) and obj.get('text').strip(): return obj['text'].strip()
        for k in ('service_response','response','result'):
            if k in obj:
                t=_find_text(obj[k])
                if t:return t
        for v in obj.values():
            t=_find_text(v)
            if t:return t
    if isinstance(obj,list):
        for v in obj:
            t=_find_text(v)
            if t:return t
    return ''

def ha_ai_task(prompt,context='',entity_id=''):
    body={'task_name':'Maestra Giorgia AI','instructions':PROMPT+'\n\n'+context+'\n\nRICHIESTA:\n'+prompt}
    if entity_id: body['entity_id']=entity_id
    out=_http_json('http://supervisor/core/api/services/ai_task/generate_data?return_response',body,_ha_headers(),240)
    text=_find_text(out.get('service_response',out))
    if not text: raise RuntimeError('AI Task Home Assistant non ha restituito testo')
    return text

def ai_generate(prompt,context=''):
    s=load_settings(); provider=(s.get('ai_provider') or 'auto').lower()
    entity=(s.get('ha_ai_task_entity') or '').strip()
    errors=[]
    if provider in ('auto','gemini'):
        try:return gemini(prompt,context)
        except Exception as e:
            errors.append(str(e))
            if provider=='gemini': raise
    if provider in ('auto','ha_task'):
        try:return ha_ai_task(prompt,context,entity)
        except Exception as e: errors.append(str(e))
    raise RuntimeError('Nessun motore AI disponibile. '+' | '.join(errors))

def gemini_tts(text,voice='Kore'):
    s=load_settings(); key=s.get('gemini_api_key','').strip()
    if not key: raise RuntimeError('Gemini API key non configurata per la voce')
    model=s.get('tts_model') or 'gemini-3.1-flash-tts-preview'
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    prompt='Leggi in italiano con tono femminile professionale, caldo e chiaro, da insegnante di scuola primaria. Testo da leggere:\n'+text[:6000]
    body={
      'contents':[{'parts':[{'text':prompt}]}],
      'generationConfig':{
        'responseModalities':['AUDIO'],
        'speechConfig':{'voiceConfig':{'prebuiltVoiceConfig':{'voiceName':voice}}}
      }
    }
    out=_http_json(url,body,{'Content-Type':'application/json'},180)
    parts=out.get('candidates',[{}])[0].get('content',{}).get('parts',[])
    inline=next((p.get('inlineData') or p.get('inline_data') for p in parts if p.get('inlineData') or p.get('inline_data')),None)
    if not inline or not inline.get('data'): raise RuntimeError('Gemini TTS non ha restituito audio')
    raw=base64.b64decode(inline['data'])
    mime=(inline.get('mimeType') or inline.get('mime_type') or '').lower()
    if 'wav' in mime:return raw
    buff=io.BytesIO()
    with wave.open(buff,'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(24000); wf.writeframes(raw)
    return buff.getvalue()

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
            if p=='/api/ha_ai_tasks': return self.sendj({'ok':True,'items':ha_ai_tasks()})
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
                payload=(b.get('eval_date') or date.today().isoformat(),int(b.get('term') or 1),b.get('subject','').strip(),b.get('activity','').strip(),b.get('grade','').strip(),int(b.get('autonomy') or 3),b.get('notes','').strip(),b.get('eval_type') or 'Orale')
                if b.get('id'):
                    store.write('UPDATE evaluations SET eval_date=?,term=?,subject=?,activity=?,grade=?,autonomy=?,notes=?,eval_type=? WHERE id=?',payload+(int(b['id']),))
                    return self.sendj({'ok':True,'id':int(b['id']),'updated':True})
                i=store.write('INSERT INTO evaluations(student_id,eval_date,term,subject,activity,grade,autonomy,notes,eval_type) VALUES(?,?,?,?,?,?,?,?,?)',(b.get('student_id'),)+payload)
                return self.sendj({'ok':True,'id':i,'updated':False})
            if p=='/api/goals':
                i=store.write('INSERT INTO goals(student_id,area,description,status,notes,updated_at) VALUES(?,?,?,?,?,?)',(b.get('student_id'),b.get('area',''),b.get('description',''),b.get('status','Da iniziare'),b.get('notes',''),now)); return self.sendj({'ok':True,'id':i})
            if p=='/api/diary':
                i=store.write('INSERT INTO diary(student_id,diary_date,category,text,participation,support_level) VALUES(?,?,?,?,?,?)',(b.get('student_id'),b.get('diary_date') or date.today().isoformat(),b.get('category','Apprendimento'),b.get('text',''),int(b.get('participation') or 3),int(b.get('support_level') or 3))); return self.sendj({'ok':True,'id':i})
            if p=='/api/ai':
                txt=ai_generate(b.get('prompt',''),store.context(b.get('student_id'))); return self.sendj({'ok':True,'text':txt,'provider':load_settings().get('ai_provider','auto')})
            if p=='/api/tts':
                voice=b.get('voice') or load_settings().get('tts_voice') or 'Kore'
                audio=gemini_tts(b.get('text',''),voice)
                self.send_response(200); self.send_header('Content-Type','audio/wav'); self.send_header('Content-Length',str(len(audio))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(audio); return
            if p=='/api/materials':
                i=store.write('INSERT INTO materials(student_id,kind,title,content,created_at) VALUES(?,?,?,?,?)',(b.get('student_id'),b.get('kind','Materiale'),b.get('title','Materiale'),b.get('content',''),now)); return self.sendj({'ok':True,'id':i})
            if p=='/api/settings':
                s=load_settings()
                for k in ('teacher_name','assistant_name','gemini_model','ai_provider','ha_ai_task_entity','tts_voice','tts_model','auto_speak'):
                    if k in b:s[k]=b[k]
                if b.get('gemini_api_key'):s['gemini_api_key']=b['gemini_api_key'].strip()
                if b.get('remove_gemini_key'):s['gemini_api_key']=''
                save_settings(s); return self.sendj({'ok':True})
            if p=='/api/test_ai':
                return self.sendj({'ok':True,'text':ai_generate('Rispondi soltanto con: Maestra collegata correttamente.')})
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
