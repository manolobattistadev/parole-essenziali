# parole essenziali

Pubblica in automatico su Instagram aforismi in grafica minimale (fondo nero, testo bianco),
a costo zero: gira su **GitHub Actions**, i media sono ospitati su **GitHub Pages** e la
pubblicazione usa l'**Instagram API** (gratuita).

## Programma

| Ora (Roma) | Contenuti                                   |
|------------|---------------------------------------------|
| 09:00      | post (1080×1350) + storia (1080×1920)       |
| 13:00      | storia + reel (solo lun, mer, ven, sab)     |
| 19:00      | post + storia (citazione da film)           |

Ogni fascia ha una citazione diversa. Post, storia e reel della stessa fascia condividono lo stesso.
Il programma si cambia in `config.json` (`programma`, `giorni_reel`).

Il reel dura 9 secondi: dissolvenza in entrata e in uscita, uno zoom lento e un sottofondo
ambient **sintetizzato al momento con ffmpeg**, quindi senza alcun problema di diritti.

## Come funziona

1. Il workflow `Pubblica` parte alle :52 delle ore UTC 6, 7, 10, 11, 16 e 17. Copre così le
   fasce sia con l'ora solare sia con quella legale.
2. `python -m bot prepara` guarda l'ora di Roma e trova la fascia dovuta (tra 15 minuti prima e
   3 ore dopo l'orario previsto), poi genera i media in `site/`.
3. I media vengono pubblicati su GitHub Pages, perché Instagram vuole un URL pubblico.
4. `python -m bot pubblica` crea i container su Instagram, attende l'elaborazione e pubblica.
5. Il registro `data/pubblicati.json` viene committato. Così nulla viene pubblicato due volte,
   un contenuto fallito si ritenta al giro successivo e il repo resta attivo. GitHub disattiva i
   cron dopo 60 giorni senza commit.

Il workflow `Controllo settimanale` ogni domenica verifica il token, lo rinnova se è di quelli che
scadono.

## Setup (una volta sola)

### 1. Instagram

1. Rendi l'account **professionale** (Creator o Business): Impostazioni → Tipo di account e strumenti.

### 2. App Meta

1. Vai su <https://developers.facebook.com/apps> → **Crea app**.
2. Tra i casi d'uso (filtro *Gestione dei contenuti*) scegli **"Gestisci messaggi e contenuti su Instagram"**.
3. **Ruoli dell'app → Ruoli → Aggiungi persone → Tester di Instagram** con lo username della pagina.
   Accetta l'invito da browser: <https://www.instagram.com/accounts/manage_access/> → *Inviti tester*.
4. **Casi d'uso → Instagram → Personalizza → API setup with Unified login**:
   - al punto **1** seleziona la configurazione *API Instagram (accesso unificato)*. Il token è
     dell'utente di sistema e **non scade**, e include `instagram_basic` e `instagram_content_publish`;
   - al punto **2** fai **Aggiungi account** → *parole.essenziali*, poi **Genera token**.
     Il numero sotto il nome dell'account (`17841…`) è l'**ID utente Instagram**.

L'app può restare in modalità sviluppo: per pubblicare sul **tuo** account non serve la review di Meta.

### 3. GitHub

1. Il repo deve essere **pubblico**: GitHub Pages è gratis solo sui repo pubblici.
2. **Settings → Pages → Source: GitHub Actions**.
3. **Settings → Secrets and variables → Actions → New repository secret**:

   | Nome              | Valore                                                        |
   |-------------------|---------------------------------------------------------------|
   | `IG_ACCESS_TOKEN` | il token del punto 2.4                                        |
   | `IG_USER_ID`      | l'ID dell'account Instagram (`17841…`)                        |
   | `GH_PAT`          | *solo per token che scadono*: fine-grained PAT con **Secrets: Read and write** |
   | `FB_APP_ID` / `FB_APP_SECRET` | *solo per token Facebook che scadono*: da Impostazioni app → Di base |

4. **Actions → Verifica token → Run workflow**: controlla il token senza pubblicare nulla.
5. **Actions → Pubblica → Run workflow** con `fascia = 09:00` per una prima pubblicazione.

Da qui in poi è tutto automatico.

Il bot riconosce da solo il tipo di token. Un token Instagram Login (`IG…`) passa da
`graph.instagram.com`, uno Facebook o dell'utente di sistema (`EA…`) da `graph.facebook.com`.
Il `Controllo settimanale` rinnova solo i token che scadono e ignora quelli di sistema.

## Uso locale

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # serve anche ffmpeg (brew install ffmpeg)
python -m bot anteprima                  # post, storia e reel di prova in out/anteprima
python -m bot anteprima --id 42          # anteprima di un aforisma specifico
```

## Raccolte

Le citazioni stanno in raccolte separate, ognuna con il suo ordine e i suoi hashtag (`raccolte` in `config.json`):

| Raccolta   | File                  | Contenuto                                                   | Fascia |
|------------|-----------------------|-------------------------------------------------------------|--------|
| `aforismi` | `data/aforismi.json`  | ~1.500 aforismi originali, circa 2 anni (nessun problema di diritti) | 09, 13 |
| `film`     | `data/film.json`      | 113 battute celebri di film dal 1994 in poi, nel testo del doppiaggio italiano | 19   |

Ogni fascia del `programma` sceglie la sua `raccolta`. Il primo giro segue l'ordine del file. Finita la
lista si ricomincia con un ordine rimescolato, diverso per ogni giro. Le citazioni aggiunte entrano
subito nel giro in corso. Per aggiungerne:

```json
{ "id": 57, "testo": "…", "autore": "Titolo del film (anno)" }
```

`autore` compare sotto il testo in grigio corsivo. Per gli aforismi originali lascialo `null`.

Le battute dei film sono state trascritte a memoria: conviene rileggerle una volta. Si usa solo il
testo, mai fotogrammi, locandine o loghi. Per eventuali citazioni d'autore usa solo autori in
pubblico dominio (morti da oltre 70 anni) con attribuzione verificata.

Per un'anteprima: `python -m bot anteprima --raccolta film --id 3`.

## Note

- I cron di GitHub possono slittare di qualche minuto, a volte di più nelle ore di punta.
- Via API non si può usare la libreria musicale di Instagram: per questo l'audio è generato.
- `post.dimensione_testo` in `config.json` regola la grandezza del testo nei post (1.0 = grande, 0.85 = attuale).
- `reel.condividi_nel_feed` in `config.json` decide se il reel appare anche nella griglia del profilo.
- Il font è Playfair Display (SIL Open Font License, vedi `fonts/OFL.txt`).

## Avvio puntuale: cron-job.org

Il cron di GitHub Actions non è affidabile: può ritardare o saltare le esecuzioni, e su questo
repo non è mai partito. Per questo il workflow `Pubblica` viene avviato da **cron-job.org** (gratuito)
con una chiamata all'API di GitHub:

- **URL:** `POST https://api.github.com/repos/manolobattistadev/parole-essenziali/actions/workflows/pubblica.yml/dispatches`
- **Header:** `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
- **Body:** `{"ref":"main"}`
- **Orario:** `0,30 9,13,19 * * *`, fuso **Europe/Rome**. La chiamata delle :30 è un recupero: il registro evita i doppioni.
- **Token:** fine-grained PAT di `manolobattistadev`, solo questo repo, permesso **Actions: Read and write**.

Il cron di GitHub resta attivo come riserva.

## Manutenzione: cosa può fermarlo

Il bot è pensato per andare avanti senza interventi. Questi sono i soli punti da tenere d'occhio:

- **Mail di GitHub "Run failed".** Arrivano all'account che ha modificato per ultimo i workflow.
  Un errore isolato si ritenta da solo al giro successivo, uno che si ripete va guardato.
- **Mail di Meta.** Meta può chiedere una volta l'anno la *Verifica dell'utilizzo dei dati*
  (Data Use Checkup) o altre conferme sull'app. Se non rispondi può limitare l'app, e il token smette di funzionare.
- **Scadenza del token di cron-job.org.** Quando scade, gli avvii si fermano: rigeneralo e aggiornalo nell'header `Authorization`.
- **Il repo deve restare pubblico**, altrimenti GitHub Pages non è più gratis.
- **Versione API** (`graph_api_version`). Quando Meta ritira una versione, le chiamate passano da
  sole alla più vecchia ancora attiva. Se un giorno qualcosa si rompe, alzare il numero è il primo tentativo.

