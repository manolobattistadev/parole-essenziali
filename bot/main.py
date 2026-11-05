"""Comandi:

  python -m bot prepara   [--fascia 09:00] [--forza]   genera i media della fascia dovuta in site/
  python -m bot pubblica  --base-url URL                pubblica su Instagram ciò che è stato preparato
  python -m bot verifica                                controlla il token e l'account collegato
  python -m bot anteprima [--raccolta film] [--id N]                   genera post/storia/reel di prova in out/anteprima
  python -m bot rinnova-token --out F                   rinnova il token e lo scrive nel file --out
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path

import requests

from . import core, render
from .instagram import Instagram, rinnova_token

SITE = core.ROOT / "site"
OUT = core.ROOT / "out"
LAVORO = OUT / "lavoro.json"
FILE = {"post": "post.jpg", "storia": "storia.jpg", "reel": "reel.mp4"}


def leggi_token() -> str:
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip().strip("\"'").strip()
    if not token:
        raise SystemExit("Manca il secret IG_ACCESS_TOKEN")
    print(f"Token: inizia con {token[:3]!r}…, {len(token)} caratteri")
    return token


def gh_output(**valori) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    for k, v in valori.items():
        print(f"{k}={v}")
        if path:
            with open(path, "a") as f:
                f.write(f"{k}={v}\n")


def genera(aforisma: dict, contenuti: list[str], cartella: Path, cfg: dict) -> None:
    cartella.mkdir(parents=True, exist_ok=True)
    firma = cfg.get("firma", "")
    if "post" in contenuti:
        render.immagine_post(aforisma, firma, cartella / FILE["post"])
    if "storia" in contenuti:
        render.immagine_storia(aforisma, firma, cartella / FILE["storia"])
    if "reel" in contenuti:
        r = cfg["reel"]
        render.reel(aforisma, firma, cartella / FILE["reel"], durata=r["durata_secondi"],
                    zoom=r["zoom_finale"], audio=r["audio"])


def cmd_prepara(args) -> None:
    cfg = core.config()
    if args.fascia:
        data = args.data or core.adesso(cfg).date().isoformat()
        fascia = core.trova_fascia(cfg, args.fascia)
    else:
        trovata = core.fascia_dovuta(cfg)
        if not trovata:
            print(f"Nessuna fascia da pubblicare alle {core.adesso(cfg):%Y-%m-%d %H:%M}.")
            gh_output(da_fare="false")
            return
        data, fascia = trovata

    contenuti = core.mancanti(data, fascia, cfg)
    if args.forza:
        contenuti = core.contenuti_fascia(fascia, dt.date.fromisoformat(data), cfg)
    if not contenuti:
        print(f"{data} {fascia['ora']}: già tutto pubblicato.")
        gh_output(da_fare="false")
        return

    raccolta = core.raccolta_di(fascia)
    aforisma = core.scegli_aforisma(data, fascia["ora"], raccolta, cfg)
    slug = f"{data}-{fascia['ora'].replace(':', '')}"
    genera(aforisma, contenuti, SITE / "m" / slug, cfg)
    (SITE / ".nojekyll").touch()
    (SITE / "index.html").write_text(f"<!doctype html><title>{cfg['nome_pagina']}</title>\n", "utf-8")

    OUT.mkdir(exist_ok=True)
    core.save_json(LAVORO, {"data": data, "fascia": fascia["ora"], "raccolta": raccolta, "aforisma": aforisma,
                            "contenuti": contenuti, "cartella": f"m/{slug}"})
    print(f"{data} {fascia['ora']} → {raccolta} #{aforisma['id']} «{aforisma['testo']}» — {', '.join(contenuti)}")
    gh_output(da_fare="true")


def attendi_url(url: str, timeout: int = 600) -> None:
    fine = time.time() + timeout
    while time.time() < fine:
        try:
            if requests.head(url, timeout=20, allow_redirects=True).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(10)
    raise SystemExit(f"{url} non raggiungibile dopo {timeout}s")


def cmd_pubblica(args) -> None:
    cfg = core.config()
    lavoro = core.load_json(LAVORO)
    data, fascia, aforisma = lavoro["data"], lavoro["fascia"], lavoro["aforisma"]
    raccolta = lavoro.get("raccolta", "aforismi")
    base = args.base_url.rstrip("/")
    caption = core.didascalia(aforisma, raccolta, cfg)

    token = leggi_token()
    ig = Instagram(token, os.environ.get("IG_USER_ID", "").strip() or None, cfg["graph_api_version"])

    core.aggiorna_registro(data, fascia, raccolta, aforisma["id"])
    errori = []
    for tipo in lavoro["contenuti"]:
        url = f"{base}/{lavoro['cartella']}/{FILE[tipo]}"
        try:
            attendi_url(url)
            if tipo == "post":
                media_id = ig.post(url, caption)
            elif tipo == "storia":
                media_id = ig.storia(url)
            else:
                media_id = ig.reel(url, caption, cfg["reel"]["condividi_nel_feed"])
        except Exception as e:  # registra i successi e prova gli altri contenuti
            print(f"✗ {tipo}: {e}", file=sys.stderr)
            errori.append(tipo)
            continue
        core.aggiorna_registro(data, fascia, raccolta, aforisma["id"], **{tipo: media_id})
        print(f"✓ {tipo} pubblicato ({media_id})")

    if errori:
        raise SystemExit(f"Non pubblicati: {', '.join(errori)} (verranno ritentati al prossimo giro)")


def cmd_anteprima(args) -> None:
    cfg = core.config()
    aforismi = core.carica_raccolta(args.raccolta, cfg)
    scelti = [a for a in aforismi if a["id"] == args.id] if args.id else [max(aforismi, key=lambda a: len(a["testo"]))]
    if not scelti:
        raise SystemExit(f"Aforisma {args.id} non trovato")
    dest = OUT / "anteprima"
    genera(scelti[0], ["post", "storia", "reel"], dest, cfg)
    print(f"Anteprima in {dest}")


def cmd_rinnova_token(args) -> None:
    token = leggi_token()
    nuovo = rinnova_token(token, core.config()["graph_api_version"],
                          os.environ.get("FB_APP_ID") or None, os.environ.get("FB_APP_SECRET") or None)
    if nuovo is None:
        return
    giorni = int(nuovo.get("expires_in") or 0) // 86400
    print(f"::add-mask::{nuovo['access_token']}")
    Path(args.out).write_text(nuovo["access_token"])
    print(f"Token rinnovato, valido per {giorni} giorni.")


def cmd_verifica(_args) -> None:
    ig = Instagram(leggi_token(), os.environ.get("IG_USER_ID", "").strip() or None,
                   core.config()["graph_api_version"])
    print(f"OK: il bot pubblicherà su @{ig.username}")


def main() -> None:
    p = argparse.ArgumentParser(prog="bot")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("prepara")
    s.add_argument("--fascia", help="forza una fascia, es. 09:00")
    s.add_argument("--data", help="YYYY-MM-DD (solo con --fascia)")
    s.add_argument("--forza", action="store_true", help="rigenera anche i contenuti già pubblicati")
    s.set_defaults(fn=cmd_prepara)
    s = sub.add_parser("pubblica")
    s.add_argument("--base-url", required=True)
    s.set_defaults(fn=cmd_pubblica)
    s = sub.add_parser("anteprima")
    s.add_argument("--id", type=int)
    s.add_argument("--raccolta", default="aforismi", help="aforismi, film, …")
    s.set_defaults(fn=cmd_anteprima)
    s = sub.add_parser("verifica")
    s.set_defaults(fn=cmd_verifica)
    s = sub.add_parser("rinnova-token")
    s.add_argument("--out", required=True, help="file in cui scrivere il nuovo token")
    s.set_defaults(fn=cmd_rinnova_token)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
