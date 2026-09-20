import json, os, sqlite3, threading, urllib.request, urllib.error, base64, io, wave, time, re, textwrap
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DATA=Path('/data'); DATA.mkdir(parents=True,exist_ok=True)
MANUAL_DIR=DATA/'manuals'; MANUAL_DIR.mkdir(parents=True,exist_ok=True)
DB=DATA/'maestra_giorgia_ai.db'; SETTINGS=DATA/'settings.json'
INDEX=Path(__file__).with_name('index.html'); PORT=8099
PROMPT="""Sei Maestra, assistente AI professionale di Giorgia Mauro per il sostegno nella scuola primaria italiana, dalla classe prima alla quinta.
La priorita assoluta e farti capire: risposte brevi, concrete, ordinate e senza giri di parole. Una frase = un concetto. Usa esempi quotidiani, passaggi numerati e supporti solo quando sono didatticamente utili.
Semplice NON significa banale: mantieni il nucleo disciplinare, la terminologia corretta e un livello adeguato alla classe. In 1a-2a privilegia concretezza e manipolazione; in 3a costruisci il ponte tra concreto e simbolico; in 4a-5a usa anche ragionamento, problemi, collegamenti e progressiva astrazione.
Adatta il modo di presentare il compito usando punti di forza, difficolta osservate, strategie efficaci e obiettivi del profilo: modula carico cognitivo, quantita di testo, numero di passaggi, grado di astrazione e tipo di consegna senza abbassare automaticamente l obiettivo curricolare.
Figure, schemi, tabelle, linee dei numeri, diagrammi e rappresentazioni devono avere una funzione didattica precisa: non usarli per decorazione e non usarli se non servono.
Per materiali rivolti all'alunno/a: NON citare mai difficolta, diagnosi, comportamenti, strategie private, note del profilo o altre informazioni riservate. Usa quel contesto solo per adattare silenziosamente livello, struttura e modalita di spiegazione.
Per la docente distingui quando utile: COSA SPIEGARE, COME DIRLO, ESEMPIO, SUPPORTO, COSA OSSERVARE. Non inventare voti, diagnosi, leggi o fatti non forniti.
Se una richiesta riguarda normativa o procedure aggiornate, tratta il testo/manuale fornito come fonte primaria e segnala quando serve verificare una fonte ufficiale.
Sii inclusiva, non stigmatizzante, professionale, pratica e concisa."""

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
            CREATE TABLE IF NOT EXISTS manuals(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,category TEXT,manual_date TEXT,source_url TEXT,tags TEXT,summary TEXT,content TEXT,attachment_name TEXT,attachment_path TEXT,created_at TEXT,updated_at TEXT);
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
            if self.db.execute("SELECT COUNT(*) FROM manuals").fetchone()[0]==0:
                now=datetime.now().isoformat(timespec='seconds')
                seed=[
                    ('De-escalation in classe - guida rapida','Comportamento','','','crisi,calma,classe','Ridurre stimoli, parlare poco e con tono calmo, offrire una scelta semplice e attendere.','1. Metti in sicurezza lo spazio.\n2. Riduci parole e richieste.\n3. Usa tono calmo e neutro.\n4. Offri due scelte semplici.\n5. Aspetta il tempo necessario.\n6. Dopo la calma, riparti con una richiesta facile.'),
                    ('Task analysis - scomporre un compito','Metodi educativi','','','task analysis,autonomia','Dividere un compito in piccoli passaggi osservabili e insegnarli uno alla volta.','Scrivi il compito finale.\nDividilo in 4-8 passaggi semplici.\nMostra un passaggio per volta.\nSegna quali passaggi sono autonomi e quali richiedono aiuto.\nRiduci gradualmente l aiuto.'),
                    ('Prompting e fading - guida pratica','Metodi educativi','','','prompting,fading,aiuto','Dare il minimo aiuto necessario e ridurlo gradualmente per aumentare autonomia.','Ordine consigliato quando possibile: indizio visivo, gesto, breve suggerimento verbale, modello.\nRiduci l aiuto appena il bambino mostra competenza.\nPremia il tentativo autonomo.'),
                    ('Routine visiva e anticipazione','Strategie pratiche','','','routine,visuale,anticipazione','Mostrare prima cosa succede riduce incertezza e richieste verbali ripetute.','Usa 3-6 immagini in ordine.\nMostra ADESSO e DOPO.\nSpunta ogni passaggio concluso.\nAvvisa prima dei cambiamenti.'),
                    ('CAA - principi operativi di base','CAA / visuale','','','caa,comunicazione,simboli','Usare simboli, immagini e parole per sostenere comprensione ed espressione.','Tieni i simboli visibili e raggiungibili.\nUsa poche alternative alla volta.\nAccompagna simbolo e parola.\nConferma ogni tentativo comunicativo.'),
                    ('Checklist per nuova normativa','Normativa scolastica','','','leggi,normativa,fonte','Scheda neutra per archiviare una nuova norma senza confonderla con interpretazioni.','Salva titolo completo, data, fonte ufficiale e link.\nIncolla il testo o il passaggio rilevante.\nAggiungi una sintesi: cosa cambia, da quando, per chi, cosa deve fare la scuola.\nNon considerare una sintesi AI come fonte ufficiale.')
                ]
                self.db.executemany("INSERT INTO manuals(title,category,manual_date,source_url,tags,summary,content,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",[x+(now,now) for x in seed])
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


def _extract_json(text):
    raw=str(text or '').strip()
    raw=raw.replace('```json','').replace('```JSON','').replace('```','').strip()
    start=raw.find('{'); end=raw.rfind('}')
    if start<0 or end<start:
        raise RuntimeError('Gemini non ha restituito JSON valido')
    return json.loads(raw[start:end+1])

def gemini_vision(mode,images,subject='',task_type='',writing_type=''):
    settings=load_settings()
    key=(settings.get('gemini_api_key') or '').strip()
    if not key:
        raise RuntimeError('Inserisci la Gemini API key nelle Impostazioni')
    model=settings.get('gemini_model') or 'gemini-3.8-flash'
    if mode=='book':
        prompt=(
            'Analizza le immagini di un libro per scuola primaria. Restituisci SOLO JSON valido con queste chiavi: '
            '{"title":"","author":"","topic":"","grade_level":"","summary_short":"","summary_simple":"","keywords":[],"questions":[]}. '
            'Riassumi solo cio che e realmente visibile nelle immagini. Se titolo o autore non sono leggibili scrivi "non leggibile". '
            'summary_short massimo 8 righe. summary_simple usa frasi brevi e parole facili. keywords massimo 6. questions massimo 5.'
        )
    elif mode=='homework':
        prompt=(
            'Analizza il compito fotografato. Materia indicata: '+str(subject or 'non specificata')+
            '. Tipo: '+str(task_type or 'compito')+
            '. Restituisci SOLO JSON valido con queste chiavi: '
            '{"subject":"","detected_text":"","errors":[{"label":"","correction":"","note":"","x":0,"y":0,"w":0,"h":0}],"strengths":[],"child_explanation":"","recovery_activity":""}. '
            'Le coordinate x,y,w,h sono da 0 a 1000 rispetto alla foto. Inserisci coordinate solo quando la zona e chiaramente localizzabile. '
            'Non inventare errori. Controlla ortografia, calcolo, procedimento e consegna in base a cio che e visibile. '
            'La spiegazione al bambino deve essere breve e rispettosa.'
        )
    elif mode=='handwriting':
        prompt=(
            'Osserva questa scrittura in ottica didattica e grafomotoria. Tipo indicato: '+str(writing_type or 'non specificato')+
            '. Restituisci SOLO JSON valido con queste chiavi: '
            '{"writing_type":"","legibility":"","spacing":"","alignment":"","letter_shape":"","motor_observations":"","strengths":[],"improvements":[],"exercises":[]}. '
            'Descrivi solo caratteristiche visibili: leggibilita, dimensione, spaziatura, rigo, regolarita, forma e continuita apparente del tratto. '
            'Non dedurre personalita, ansia, intelligenza, diagnosi, DSA o altre condizioni cliniche. Massimo 5 esercizi pratici.'
        )
    else:
        raise RuntimeError('Modalita visione non valida')

    parts=[{'text':PROMPT+'\\n\\n'+prompt}]
    for image in (images or [])[:6]:
        data=(image.get('data') or '').strip() if isinstance(image,dict) else ''
        if not data:
            continue
        mime=(image.get('mime') or 'image/jpeg') if isinstance(image,dict) else 'image/jpeg'
        parts.append({'inlineData':{'mimeType':mime,'data':data}})
    if len(parts)==1:
        raise RuntimeError('Nessuna immagine ricevuta')

    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    body={'contents':[{'parts':parts}],'generationConfig':{'temperature':0.2}}
    out=_http_json(url,body,{'Content-Type':'application/json'},240)
    text=''.join(p.get('text','') for p in out.get('candidates',[{}])[0].get('content',{}).get('parts',[])).strip()
    if not text:
        raise RuntimeError(out.get('error',{}).get('message','Gemini Vision non ha restituito una risposta'))
    return _extract_json(text)

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


def _safe_filename(value, fallback='documento'):
    value=re.sub(r'[^A-Za-z0-9._-]+','_',str(value or '').strip()).strip('._')
    return value[:90] or fallback

def _pdf_clean(value):
    return str(value or '').replace('\r','').encode('latin-1','replace').decode('latin-1')

def _pdf_escape(value):
    return _pdf_clean(value).replace('\\','\\\\').replace('(','\\(').replace(')','\\)')

def _pdf_text_cmd(x,y,text,size=10,bold=False):
    font='F2' if bold else 'F1'
    return f"BT /{font} {size} Tf 1 0 0 1 {x:.1f} {y:.1f} Tm ({_pdf_escape(text)}) Tj ET\n"

def _pdf_make(pages):
    # PDF minimale A4, Helvetica/Helvetica-Bold, nessuna dipendenza esterna.
    objects=[None,
        "<< /Type /Catalog /Pages 2 0 R >>",
        None,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    ]
    page_refs=[]
    for commands in pages:
        content=''.join(commands).encode('latin-1','replace')
        content_obj=len(objects)
        objects.append(b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"endstream")
        page_obj=len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_obj} 0 R >>")
        page_refs.append(page_obj)
    objects[2]="<< /Type /Pages /Kids ["+' '.join(f'{x} 0 R' for x in page_refs)+f"] /Count {len(page_refs)} >>"

    out=bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets=[0]*len(objects)
    for i in range(1,len(objects)):
        offsets[i]=len(out)
        obj=objects[i]
        data=obj if isinstance(obj,(bytes,bytearray)) else obj.encode('latin-1','replace')
        out.extend(f"{i} 0 obj\n".encode()); out.extend(data); out.extend(b"\nendobj\n")
    xref=len(out)
    out.extend(f"xref\n0 {len(objects)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for i in range(1,len(objects)):
        out.extend(f"{offsets[i]:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(out)

def _wrapped_lines(text,width=92):
    lines=[]
    for raw in _pdf_clean(text).splitlines():
        raw=raw.strip()
        if not raw:
            lines.append(''); continue
        if raw.startswith(('### ','## ')):
            raw=raw.lstrip('#').strip().upper()
        prefix='- ' if raw.startswith(('• ','- ')) else ''
        if prefix: raw=raw[2:].strip()
        wrapped=textwrap.wrap(raw,width=width,break_long_words=False,replace_whitespace=False) or ['']
        lines.extend([(prefix if i==0 else '  ')+part for i,part in enumerate(wrapped)])
    return lines

def material_pdf(title,content,student_name='',kind='Materiale'):
    pages=[]; cmds=[]; y=800
    def new_page():
        nonlocal cmds,y
        if cmds: pages.append(cmds)
        cmds=[]; y=800
        cmds.append(_pdf_text_cmd(45,y,'GM Maestra AI',20,True)); y-=28
        cmds.append(_pdf_text_cmd(45,y,title or kind,14,True)); y-=20
        meta=[]
        if student_name: meta.append('Alunno/a: '+student_name)
        if kind: meta.append('Tipo: '+kind)
        if meta: cmds.append(_pdf_text_cmd(45,y,' - '.join(meta),9,False)); y-=22
        cmds.append("0.88 0.90 0.96 RG 45 %.1f m 550 %.1f l S\n"%(y,y)); y-=18
    new_page()
    for line in _wrapped_lines(content,92):
        if y<55: new_page()
        if not line:
            y-=8; continue
        is_heading=line.isupper() and len(line)<80
        cmds.append(_pdf_text_cmd(48,y,line,11 if is_heading else 10,is_heading))
        y-=17 if is_heading else 14
    if cmds: pages.append(cmds)
    return _pdf_make(pages)

def _grade_num(value):
    m=re.search(r'\d+(?:[\.,]\d+)?',str(value or ''))
    if not m:return None
    try:return float(m.group(0).replace(',','.'))
    except:return None

def _eval_type(row):
    t=(row.get('eval_type') or '').strip()
    a=(row.get('activity') or '').strip().lower()
    if (not t or t=='Orale') and ('verifica' in a or a in ('scritta','scritto')): return 'Scritta'
    return t or ('Orale' if ('oral' in a or 'interrog' in a) else 'Osservazione')

def evaluation_pdf(student_name,period_label,items):
    pages=[]; first=[]; y=800
    first.append(_pdf_text_cmd(45,y,'Report valutazioni',20,True)); y-=28
    first.append(_pdf_text_cmd(45,y,student_name,15,True)); y-=20
    first.append(_pdf_text_cmd(45,y,period_label,9,False)); y-=26

    numeric=[x for x in items if _grade_num(x.get('grade')) is not None]
    if numeric:
        by_subject={}
        for x in numeric:
            name=(x.get('subject') or 'Altro').strip().title()
            by_subject.setdefault(name,[]).append(_grade_num(x.get('grade')))
        rows=sorted([(k,sum(v)/len(v)) for k,v in by_subject.items()])
        first.append(_pdf_text_cmd(45,y,'Media per materia',13,True)); y-=20
        for name,val in rows[:10]:
            if y<420: break
            first.append(_pdf_text_cmd(45,y,name,9,False))
            bar_x=180; bar_w=300*(max(0,min(10,val))/10)
            first.append(f"0.44 0.50 0.95 rg {bar_x} {y-3:.1f} {bar_w:.1f} 13 re f\n")
            first.append(_pdf_text_cmd(490,y,f'{val:.1f}',9,True)); y-=24

        ordered=sorted(numeric,key=lambda x:(x.get('eval_date') or '',x.get('id') or 0))
        if len(ordered)>=2 and y>255:
            y-=6; first.append(_pdf_text_cmd(45,y,'Andamento nel tempo',13,True)); y-=18
            x0,x1=55,540; yy0,yy1=y-150,y
            for tick in range(0,11,2):
                py=yy0+(tick/10)*(yy1-yy0)
                first.append(f"0.92 0.91 0.95 RG {x0} {py:.1f} m {x1} {py:.1f} l S\n")
                first.append(_pdf_text_cmd(34,py-3,str(tick),7,False))
            pts=[]
            for i,row in enumerate(ordered):
                xx=x0+(i/(len(ordered)-1))*(x1-x0)
                val=max(0,min(10,_grade_num(row.get('grade'))))
                py=yy0+(val/10)*(yy1-yy0); pts.append((xx,py,row))
            for (xa,ya,_),(xb,yb,__) in zip(pts,pts[1:]):
                first.append(f"0.33 0.47 0.91 RG 2 w {xa:.1f} {ya:.1f} m {xb:.1f} {yb:.1f} l S\n")
            for xx,py,row in pts:
                if _eval_type(row)=='Scritta':
                    first.append(f"0.90 0.42 0.65 rg {xx-3:.1f} {py-3:.1f} 6 6 re f\n")
                else:
                    first.append(f"0.33 0.47 0.91 rg {xx-3:.1f} {py-3:.1f} 6 6 re f\n")
            y=yy0-26
    pages.append(first)

    sorted_items=sorted(items,key=lambda r:(r.get('eval_date') or '',r.get('id') or 0),reverse=True)
    per_page=28
    for start in range(0,max(1,len(sorted_items)),per_page):
        chunk=sorted_items[start:start+per_page]
        cmds=[]; y=800
        cmds.append(_pdf_text_cmd(45,y,'Valutazioni - '+student_name,15,True)); y-=26
        cols=[(45,'Data'),(135,'Materia'),(315,'Tipo prova'),(455,'Voto')]
        for x,label in cols: cmds.append(_pdf_text_cmd(x,y,label,9,True))
        y-=12; cmds.append(f"0.82 0.84 0.90 RG 45 {y:.1f} m 550 {y:.1f} l S\n"); y-=15
        if not chunk:
            cmds.append(_pdf_text_cmd(45,y,'Nessuna valutazione nel periodo selezionato.',10,False))
        for row in chunk:
            subject=(row.get('subject') or '').strip().title()
            if len(subject)>27: subject=subject[:24]+'...'
            values=[(45,row.get('eval_date') or ''),(135,subject),(315,_eval_type(row)),(455,row.get('grade') or '')]
            for x,val in values: cmds.append(_pdf_text_cmd(x,y,val,9,False))
            y-=20; cmds.append(f"0.93 0.93 0.95 RG 45 {y+6:.1f} m 550 {y+6:.1f} l S\n")
        pages.append(cmds)
    return _pdf_make(pages)

def _manual_file_name(name):
    name=Path(str(name or 'allegato.pdf')).name
    stem=re.sub(r'[^A-Za-z0-9._-]+','_',name).strip('._')
    return stem[:120] or 'allegato.pdf'

def _extract_json_object(text):
    raw=str(text or '').strip()
    if raw.startswith('\\x60\\x60\\x60'):
        raw=raw.split('\\n',1)[1] if '\\n' in raw else raw
    if raw.endswith('\\x60\\x60\\x60'):
        raw=raw[:-3]
    a=raw.find('{'); b=raw.rfind('}')
    if a<0 or b<a: raise RuntimeError('La mappa AI non ha restituito JSON valido')
    return json.loads(raw[a:b+1])

def concept_map_generate(topic,student_context='',level='semplice'):
    prompt="Crea una MAPPA CONCETTUALE VISIVA professionale per scuola primaria, adeguata alla classe indicata nel profilo.\\nArgomento: "+str(topic)+"\\nLivello di spiegazione richiesto: "+str(level)+"\\nRegole: massimo 6 rami; ogni ramo massimo 3 sotto-concetti; usa parole chiave concise ma disciplinarmente corrette. 1a-2a: piu concreta; 3a: ponte concreto-simbolico; 4a-5a: relazioni tra concetti e terminologia adeguata, senza infantilizzare. Lo schema deve chiarire relazioni o passaggi, non essere decorativo. Usa emoji solo se utili. Non riportare difficolta, diagnosi o note private dell alunno. Restituisci SOLO JSON valido nel formato: {\\\"title\\\":\\\"titolo breve\\\",\\\"branches\\\":[{\\\"label\\\":\\\"ramo\\\",\\\"emoji\\\":\\\"🔹\\\",\\\"children\\\":[\\\"idea 1\\\",\\\"idea 2\\\"]}]}"
    data=_extract_json_object(ai_generate(prompt,student_context))
    title=str(data.get('title') or topic)[:80]
    branches=[]
    for branch in (data.get('branches') or [])[:6]:
        if not isinstance(branch,dict): continue
        branches.append({'label':str(branch.get('label') or '')[:50],'emoji':str(branch.get('emoji') or '🔹')[:4],'children':[str(x)[:55] for x in (branch.get('children') or [])[:3]]})
    if not branches: raise RuntimeError('La mappa non contiene rami validi')
    return {'title':title,'branches':branches}

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
            if p=='/api/manuals':
                qv=(q.get('q',[''])[0] or '').strip().lower()
                items=store.all('SELECT * FROM manuals ORDER BY coalesce(manual_date,updated_at) DESC,id DESC')
                if qv:
                    items=[x for x in items if qv in (' '.join(str(x.get(k) or '') for k in ('title','category','tags','summary','content'))).lower()]
                return self.sendj({'ok':True,'items':items})
            if p=='/api/manual_file':
                mid=q.get('id',[None])[0]
                row=store.one('SELECT attachment_name,attachment_path FROM manuals WHERE id=?',(mid,)) if mid else None
                if not row or not row.get('attachment_path'): return self.sendj({'ok':False,'error':'Allegato non trovato'},404)
                path=Path(row['attachment_path'])
                if not path.exists(): return self.sendj({'ok':False,'error':'File non trovato'},404)
                raw=path.read_bytes(); name=_manual_file_name(row.get('attachment_name'))
                self.send_response(200); self.send_header('Content-Type','application/pdf'); self.send_header('Content-Disposition','attachment; filename="'+name+'"'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw); return
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
                if b.get('id'):
                    store.write('UPDATE materials SET student_id=?,kind=?,title=?,content=? WHERE id=?',(b.get('student_id'),b.get('kind','Materiale'),b.get('title','Materiale'),b.get('content',''),int(b['id'])))
                    return self.sendj({'ok':True,'id':int(b['id']),'updated':True})
                i=store.write('INSERT INTO materials(student_id,kind,title,content,created_at) VALUES(?,?,?,?,?)',(b.get('student_id'),b.get('kind','Materiale'),b.get('title','Materiale'),b.get('content',''),now)); return self.sendj({'ok':True,'id':i,'updated':False})
            if p=='/api/material_pdf':
                sid=b.get('student_id'); student=store.one('SELECT name FROM students WHERE id=?',(sid,)) if sid else None
                title=b.get('title') or b.get('kind') or 'Materiale'
                pdf=material_pdf(title,b.get('content',''),student.get('name','') if student else '',b.get('kind') or 'Materiale')
                filename=_safe_filename(title,'materiale')+'.pdf'
                self.send_response(200); self.send_header('Content-Type','application/pdf'); self.send_header('Content-Disposition',f'attachment; filename="{filename}"'); self.send_header('Content-Length',str(len(pdf))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(pdf); return
            if p=='/api/evaluation_pdf':
                sid=b.get('student_id'); student=store.one('SELECT name FROM students WHERE id=?',(sid,)) if sid else None
                if not student: raise RuntimeError('Seleziona un alunno')
                items=b.get('items') or []
                pdf=evaluation_pdf(student.get('name','Alunno'),b.get('period_label') or 'Periodo selezionato',items)
                filename=_safe_filename('Valutazioni_'+student.get('name','Alunno'),'valutazioni')+'.pdf'
                self.send_response(200); self.send_header('Content-Type','application/pdf'); self.send_header('Content-Disposition',f'attachment; filename="{filename}"'); self.send_header('Content-Length',str(len(pdf))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(pdf); return
            if p=='/api/vision':
                result=gemini_vision(
                    b.get('mode',''),
                    b.get('images') or [],
                    b.get('subject',''),
                    b.get('task_type',''),
                    b.get('writing_type','')
                )
                return self.sendj({'ok':True,'result':result})
            if p=='/api/settings':
                s=load_settings()
                for k in ('teacher_name','assistant_name','gemini_model','ai_provider','ha_ai_task_entity','tts_voice','tts_model','auto_speak'):
                    if k in b:s[k]=b[k]
                if b.get('gemini_api_key'):s['gemini_api_key']=b['gemini_api_key'].strip()
                if b.get('remove_gemini_key'):s['gemini_api_key']=''
                save_settings(s); return self.sendj({'ok':True})
            if p=='/api/test_ai':
                return self.sendj({'ok':True,'text':ai_generate('Rispondi soltanto con: Maestra collegata correttamente.')})
            if p=='/api/concept_map':
                sid=b.get('student_id'); data=concept_map_generate(b.get('topic',''),store.context(sid) if sid else '',b.get('level') or 'semplice')
                return self.sendj({'ok':True,'map':data})
            if p=='/api/manuals':
                now=datetime.now().isoformat(timespec='seconds'); mid=b.get('id')
                title=b.get('title','').strip()
                if not title: raise RuntimeError('Inserisci il titolo del manuale')
                vals=(title,b.get('category','').strip(),b.get('manual_date','').strip(),b.get('source_url','').strip(),b.get('tags','').strip(),b.get('summary','').strip(),b.get('content','').strip())
                if mid:
                    store.write('UPDATE manuals SET title=?,category=?,manual_date=?,source_url=?,tags=?,summary=?,content=?,updated_at=? WHERE id=?',vals+(now,int(mid))); manual_id=int(mid)
                else:
                    manual_id=store.write('INSERT INTO manuals(title,category,manual_date,source_url,tags,summary,content,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',vals+(now,now))
                if b.get('attachment_b64'):
                    raw=base64.b64decode(b.get('attachment_b64'))
                    if len(raw)>12*1024*1024: raise RuntimeError('PDF troppo grande: massimo 12 MB')
                    name=_manual_file_name(b.get('attachment_name') or 'manuale.pdf'); target=MANUAL_DIR/(str(manual_id)+'_'+name); target.write_bytes(raw)
                    store.write('UPDATE manuals SET attachment_name=?,attachment_path=?,updated_at=? WHERE id=?',(name,str(target),now,manual_id))
                return self.sendj({'ok':True,'id':manual_id})
            if p=='/api/manual_summary':
                content=(b.get('content') or '').strip()
                if not content: raise RuntimeError('Incolla il testo del manuale o della norma')
                prompt='Sintetizza questo testo per una docente di sostegno primaria. Sii molto concisa. Restituisci esattamente: 1) COSA DICE in 3 punti; 2) COSA CAMBIA; 3) COSA FARE IN CLASSE/SCUOLA; 4) COSA VERIFICARE SU FONTE UFFICIALE. Non inventare nulla oltre il testo fornito.\n\nTESTO:\n'+content[:18000]
                return self.sendj({'ok':True,'text':ai_generate(prompt,'')})
            return self.sendj({'ok':False,'error':'Endpoint non trovato'},404)
        except urllib.error.HTTPError as e:
            try:d=e.read().decode()
            except:d=str(e)
            return self.sendj({'ok':False,'error':d},502)
        except Exception as e:return self.sendj({'ok':False,'error':str(e)},400)
    def do_DELETE(self):
        try:
            a=self.route_path().strip('/').split('/')
            mp={'students':'students','evaluations':'evaluations','goals':'goals','diary':'diary','materials':'materials','manuals':'manuals'}
            if len(a)!=3 or a[1] not in mp:return self.sendj({'ok':False,'error':'Risorsa non valida'},404)
            store.write(f'DELETE FROM {mp[a[1]]} WHERE id=?',(int(a[2]),)); return self.sendj({'ok':True})
        except Exception as e:return self.sendj({'ok':False,'error':str(e)},400)

if __name__=='__main__':
    print(f'Maestra Giorgia AI su 0.0.0.0:{PORT}',flush=True)
    ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
