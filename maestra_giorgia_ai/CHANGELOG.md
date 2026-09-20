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
