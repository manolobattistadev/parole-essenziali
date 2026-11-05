"""Configurazione, programma delle uscite, aforismi e registro delle pubblicazioni."""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
REGISTRO_PATH = ROOT / "data" / "pubblicati.json"
FONTS = ROOT / "fonts"

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def config() -> dict:
    return load_json(CONFIG_PATH)


def adesso(cfg: dict) -> dt.datetime:
    return dt.datetime.now(ZoneInfo(cfg["timezone"]))


def contenuti_fascia(fascia: dict, giorno: dt.date, cfg: dict) -> list[str]:
    """I contenuti di una fascia per quel giorno (il reel solo nei giorni previsti)."""
    nome_giorno = GIORNI[giorno.weekday()]
    return [c for c in fascia["contenuti"] if c != "reel" or nome_giorno in cfg["giorni_reel"]]


def registro() -> list[dict]:
    return load_json(REGISTRO_PATH) if REGISTRO_PATH.exists() else []


def _chiave(v: dict) -> tuple[str, str]:
    return (v["data"], v["fascia"])


def voce_di(data: str, fascia: str, reg: list[dict]) -> dict | None:
    return next((v for v in reg if _chiave(v) == (data, fascia)), None)


def mancanti(data: str, fascia: dict, cfg: dict) -> list[str]:
    """Contenuti della fascia non ancora pubblicati."""
    voce = voce_di(data, fascia["ora"], registro()) or {}
    giorno = dt.date.fromisoformat(data)
    return [c for c in contenuti_fascia(fascia, giorno, cfg) if not voce.get(c)]


def fascia_dovuta(cfg: dict, ora: dt.datetime | None = None) -> tuple[str, dict] | None:
    """La fascia da pubblicare adesso: già iniziata (con un piccolo anticipo), non troppo
    vecchia e con contenuti ancora da pubblicare. Se più d'una, la più recente."""
    ora = ora or adesso(cfg)
    anticipo = dt.timedelta(minutes=cfg.get("anticipo_minuti", 15))
    ritardo = dt.timedelta(minutes=cfg.get("ritardo_massimo_minuti", 180))
    data = ora.date().isoformat()
    candidate = []
    for fascia in cfg["programma"]:
        h, m = map(int, fascia["ora"].split(":"))
        inizio = ora.replace(hour=h, minute=m, second=0, microsecond=0)
        if inizio - anticipo <= ora <= inizio + ritardo and mancanti(data, fascia, cfg):
            candidate.append((inizio, fascia))
    if not candidate:
        return None
    return data, max(candidate, key=lambda c: c[0])[1]


def trova_fascia(cfg: dict, ora_fascia: str) -> dict:
    for f in cfg["programma"]:
        if f["ora"] == ora_fascia:
            return f
    raise SystemExit(f"Fascia {ora_fascia!r} non presente nel programma")


def raccolta_di(fascia: dict) -> str:
    return fascia.get("raccolta", "aforismi")


def _raccolta_voce(v: dict) -> str:
    return v.get("raccolta", "aforismi")


def carica_raccolta(nome: str, cfg: dict) -> list[dict]:
    if nome not in cfg["raccolte"]:
        raise SystemExit(f"Raccolta {nome!r} non definita in config.json")
    elementi = load_json(ROOT / cfg["raccolte"][nome]["file"])
    if not elementi:
        raise SystemExit(f"La raccolta {nome!r} è vuota")
    return elementi


def scegli_aforisma(data: str, fascia: str, raccolta: str, cfg: dict) -> dict:
    """La citazione della fascia. Se è già assegnata la riusa. Altrimenti sceglie la prossima
    non ancora uscita nel giro corrente: il primo giro segue l'ordine del file, i successivi
    un ordine rimescolato (diverso per ogni giro). Le citazioni aggiunte al file entrano subito."""
    elementi = carica_raccolta(raccolta, cfg)
    per_id = {a["id"]: a for a in elementi}
    reg = registro()

    voce = voce_di(data, fascia, reg)
    if voce and _raccolta_voce(voce) == raccolta and voce["id"] in per_id:
        return per_id[voce["id"]]

    giro, usati = 0, set()
    for v in sorted(reg, key=_chiave):
        if _chiave(v) >= (data, fascia) or _raccolta_voce(v) != raccolta or v["id"] not in per_id:
            continue
        usati.add(v["id"])
        if usati >= per_id.keys():
            giro, usati = giro + 1, set()

    ordine = list(elementi)
    if giro:
        random.Random(f"{raccolta}-{giro}").shuffle(ordine)
    return next(a for a in ordine if a["id"] not in usati)


def aggiorna_registro(data: str, fascia: str, raccolta: str, aforisma_id: int, **campi) -> dict:
    reg = registro()
    voce = voce_di(data, fascia, reg)
    if voce is None:
        voce = {"data": data, "fascia": fascia}
        reg.append(voce)
        reg.sort(key=_chiave)
    voce.update({"raccolta": raccolta, "id": aforisma_id})
    voce.update({k: v for k, v in campi.items() if v is not None})
    save_json(REGISTRO_PATH, reg)
    return voce


def didascalia(aforisma: dict, raccolta: str, cfg: dict) -> str:
    testo = f"«{aforisma['testo']}»"
    if aforisma.get("autore"):
        testo += f"\n— {aforisma['autore']}"
    hashtag = cfg["raccolte"][raccolta].get("hashtag", [])
    return f"{testo}\n\n{' '.join(hashtag)}".rstrip()
