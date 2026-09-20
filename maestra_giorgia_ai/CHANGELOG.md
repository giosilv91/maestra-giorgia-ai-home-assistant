# 1.5.5
- Adattamento didattico professionale dalla classe 1a alla 5a primaria.
- Maestra usa classe, punti di forza, difficolta osservate, strategie efficaci e obiettivi per calibrare struttura e carico senza abbassare automaticamente il livello curricolare.
- Nuovo Supporto didattico: Automatico, Nessuno, Figure/rappresentazioni, Schema, Figure + schema.
- In Automatico i supporti vengono usati solo se migliorano davvero la comprensione dell argomento.
- 1a-2a: maggiore concretezza; 3a: ponte concreto-simbolico; 4a-5a: terminologia disciplinare, ragionamento, problemi, collegamenti e progressiva astrazione.
- Eliminati i suggerimenti rapidi troppo banali; sostituiti con esercizi graduati, ragionamento, riduzione del carico verbale, procedura e controllo finale.
- Le difficolta private del profilo non compaiono mai nel materiale consegnato all alunno.
- Mappe concettuali rese piu professionali e adeguate alla classe.

# 1.5.4
- Archivio materiali completo nella pagina Materiali.
- Ogni materiale salvato puo essere aperto, modificato, rinominato, esportato in PDF o eliminato.
- Conferma obbligatoria prima dell eliminazione.
- Modifica manuale del testo con editor dedicato.
- Salva modifiche sovrascrive il materiale selezionato invece di crearne uno duplicato.
- Nuovo campo Modifiche richieste / personalizzazione.
- Pulsanti rapidi: mele, euro, piu semplice, piu corto, piu esercizi.
- Rigenera con modifiche usa le preferenze scritte dalla docente.
- Nessuna modifica ai dati gia salvati.

# 1.5.3
- Fotocamera live direttamente dentro Maestra Giorgia AI.
- Pulsante Scatta copertina per Libro AI.
- Pulsante Aggiungi pagina per fotografare piu pagine.
- Pulsante Scatta compito per Analizza compiti.
- Pulsante Scatta scrittura per Calligrafia.
- Anteprima live, Scatta, Cambia camera e Chiudi.
- Usa la fotocamera posteriore come predefinita e permette il passaggio a quella anteriore.
- Se la WebView di Home Assistant non consente la fotocamera live, passa automaticamente alla fotocamera/selettore del dispositivo.
- Nessuna modifica al database o ai dati degli alunni.

# 1.5.2
- Ripristinata Fotocamera AI sopra la base stabile 1.5.1 senza modificare il database.
- Nuovo tasto 📷 Fotocamera AI nel menu.
- Libro AI: copertina + fino a 5 pagine, riassunto breve, versione facile, parole chiave e domande.
- Analizza compiti: foto da fotocamera, materia/tipo prova, errori visibili, correzioni e mini recupero.
- Evidenziazione degli errori direttamente sulla foto quando Gemini restituisce una zona attendibile.
- Salvataggio PNG del compito annotato.
- Calligrafia: osservazione didattica/grafomotoria di leggibilita, spaziatura, rigo, forma e regolarita.
- Nessuna inferenza di personalita, diagnosi, intelligenza o condizioni cliniche dalla grafia.
- PDF testuali diretti per Libro AI, Compiti e Calligrafia; le immagini si salvano separatamente sul dispositivo.
- Nessuna nuova dipendenza del container.

# 1.5.0
- Nuovo modulo Libro AI con fotocamera/copertina e fino a 6 immagini/pagine.
- Gemini Vision riconosce titolo/autore quando leggibili e riassume solo le pagine realmente fotografate.
- Riassunto breve, versione facilitata, parole chiave, domande e mappa veloce.
- Nuovo modulo Analizza compiti con foto da fotocamera, Italiano/Matematica e altre materie.
- Evidenzia sull'immagine le zone degli errori quando sono chiaramente localizzabili.
- Correzioni concise, spiegazione per il bambino e mini esercizio di recupero.
- Salvataggio PNG dell'immagine con errori evidenziati.
- Nuovo modulo Calligrafia per osservazione didattica/grafomotoria: leggibilita, spaziatura, rigo, forma, regolarita e esercizi.
- La calligrafia non viene usata per dedurre personalita, diagnosi, intelligenza o condizioni cliniche.
- Archivio persistente per analisi libri, compiti e calligrafia.
- PDF diretti sul dispositivo con immagini JPEG incorporate e testo dell'analisi.
- Nessuna dipendenza esterna aggiunta al container.

# 1.4.0
- Maestra risponde in modo piu breve, chiaro e concreto, con una frase per concetto.
- Le informazioni private dell alunno non vengono piu riportate nei materiali rivolti al bambino.
- Mappe concettuali visuali vere con rami, parole chiave, emoji e sotto-concetti.
- Salvataggio mappe come PNG e SVG sul dispositivo.
- Nuovo livello di spiegazione: molto semplice, semplice, standard.
- Nuova sezione Intervento rapido con risposte pratiche su agitazione, blocco, attenzione, rifiuto del compito e altre situazioni.
- Nuova sezione Manuali e riferimenti con ricerca, categorie, fonte, data, tag, testo, sintesi e PDF allegato.
- Possibilita di aggiungere nuove leggi, procedure e strategie comportamentali e sintetizzarle con Maestra senza inventare oltre il testo fornito.
- Manuali base inclusi: de-escalation, task analysis, prompting/fading, routine visive, CAA e checklist nuova normativa.

# 1.3.2
- Corretto errore di build della 1.3.1.
- Rimossa la dipendenza ReportLab che causava problemi su Home Assistant/Alpine.
- PDF generati ora con Python puro, senza pacchetti esterni.
- Restano Salva PDF sul dispositivo per materiali e report valutazioni con grafici.

# 1.3.1
- Salvataggio PDF diretto sul dispositivo, senza finestra di stampa.
- PDF per schede operative, verifiche, mappe concettuali, attività semplificate, storie sociali e CAA/visuale.
- Report valutazioni PDF diretto con nome alunno/a, grafici, materie, tipo prova e voti.
- Nessun dato privato del profilo viene inserito nel report valutazioni.

# 1.3.0
- Eliminata la doppia colonna Orale/Orale nel registro: resta un solo Tipo prova.
- Migrazione automatica dei vecchi record: Verifica viene riconosciuta come Scritta.
- Data della valutazione selezionabile anche per giorni precedenti o futuri.
- Pulsante Modifica per correggere data, materia, tipo prova, voto, autonomia e note.
- Report stampabile/PDF con solo nome e cognome, periodo, grafici, materie, tipo prova e voti.
- Difficoltà, strategie, PEI e note private non vengono mai incluse nel report di stampa.
- Normalizzazione nomi materia per evitare barre duplicate nei grafici.

# 1.2.0
- Gemini TTS reale con voci selezionabili, indipendente dalle voci del browser Android.
- Lettura automatica opzionale delle risposte.
- AI Task Home Assistant come motore alternativo/locale e fallback automatico.
- Retry Gemini su 429/5xx e gestione errori/timeout: niente più 'sta pensando' infinito.
- Valutazioni con tipo prova Orale/Scritta/Pratica/Osservazione.
- Grafico andamento per 30 giorni, 12 settimane, 12 mesi o anno scolastico.
- Grafico media per tutte le materie e medie orale/scritto.

# 1.1.0
- Intro animata con libro prima della Home.
- Nuovo design Home e nuovo nucleo visivo di Maestra.
- Selettore voci disponibili con priorità alle voci italiane/femminili.
- Pulsante prova voce.
- Migliorie grafiche mobile.

# 1.0.5
- Corretto errore `'str' object is not callable` nel router HTTP.
- Corretto accesso alle API interne con Ingress.

# 1.0.4
- Repository Home Assistant ufficiale.
- Struttura app completa.
- Ingress e API Home Assistant.
- Gemini e database locale persistente.
- Profili alunni, valutazioni, obiettivi, diario e materiali AI.
