# parole essenziali

Pubblica in automatico su Instagram aforismi in grafica minimale (fondo nero, testo bianco),
a costo zero: gira su **GitHub Actions**, i media sono ospitati su **GitHub Pages** e la
pubblicazione usa l'**Instagram API** (gratuita).

## Programma

| Ora (Roma) | Contenuti                                   |
|------------|---------------------------------------------|
| 09:00      | post (1080×1350) + storia (1080×1920)       |
| 13:00      | storia + reel (solo lun, mer, ven, sab)     |
| 19:00      | post + storia                               |

Ogni fascia ha un aforisma diverso. Post, storia e reel della stessa fascia condividono lo stesso.
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

Il workflow `Rinnova token Instagram` rinnova ogni domenica il token, che dura 60 giorni, e lo
salva da solo nei Secrets.

## Setup (una volta sola)

### 1. Instagram

1. Rendi l'account **professionale** (Creator o Business): Impostazioni → Tipo di account e strumenti.

### 2. App Meta

1. Vai su <https://developers.facebook.com/apps> → **Crea app**.
2. Come caso d'uso scegli **"Gestisci messaggi e contenuti su Instagram"** (Instagram API), tipo **Business**.
3. Nel pannello dell'app: **Instagram → Configurazione dell'API con l'accesso a Instagram**.
4. In **Ruoli dell'app → Ruoli** aggiungi il tuo account Instagram come **Tester di Instagram**.
   Poi accetta l'invito dall'app Instagram: Impostazioni → Autorizzazioni sito web →
   App e siti web → Inviti tester.
5. Torna in *Configurazione dell'API* → **Genera token** accanto al tuo account, e accedi.
   Ottieni un **token long-lived (60 giorni)** con i permessi `instagram_business_basic` e
   `instagram_business_content_publish`. Copia anche l'**ID utente Instagram** mostrato lì.

L'app può restare in modalità sviluppo: per pubblicare sul **tuo** account non serve la review di Meta.

### 3. GitHub

1. Il repo deve essere **pubblico**: GitHub Pages è gratis solo sui repo pubblici.
2. **Settings → Pages → Source: GitHub Actions**.
3. Crea un **fine-grained personal access token** (<https://github.com/settings/personal-access-tokens>).
   Limitalo a questo repo e dagli il permesso **Secrets: Read and write**. Serve per salvare il
   token Instagram rinnovato.
4. **Settings → Secrets and variables → Actions → New repository secret**:

   | Nome              | Valore                                       |
   |-------------------|----------------------------------------------|
   | `IG_ACCESS_TOKEN` | il token Instagram del punto 2.5             |
   | `IG_USER_ID`      | l'ID utente Instagram (facoltativo)          |
   | `GH_PAT`          | il personal access token del punto 3.3       |

5. **Actions → Pubblica → Run workflow** con `fascia = 09:00` per una prima prova.
   Il token deve avere almeno 24 ore prima che il rinnovo funzioni.

Da qui in poi è tutto automatico.

## Uso locale

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # serve anche ffmpeg (brew install ffmpeg)
python -m bot anteprima                  # post, storia e reel di prova in out/anteprima
python -m bot anteprima --id 42          # anteprima di un aforisma specifico
```

## Aforismi

Sono in `data/aforismi.json` e sono **originali**, quindi senza diritti né attribuzioni dubbie.
Escono in ordine e, finita la lista, si ricomincia. Per aggiungerne:

```json
{ "id": 120, "testo": "…", "autore": null }
```

Con 3 aforismi al giorno, 119 aforismi bastano per circa 40 giorni prima di ripetersi.
Se aggiungi citazioni di altri, usa solo autori in pubblico dominio (morti da oltre 70 anni) con
attribuzione verificata, e metti il nome in `autore`.

## Note

- I cron di GitHub possono slittare di qualche minuto, a volte di più nelle ore di punta.
- Via API non si può usare la libreria musicale di Instagram: per questo l'audio è generato.
- `reel.condividi_nel_feed` in `config.json` decide se il reel appare anche nella griglia del profilo.
- Il font è Playfair Display (SIL Open Font License, vedi `fonts/OFL.txt`).
