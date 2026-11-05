"""Instagram API — pubblicazione di post, storie e reel, rinnovo del token.

Funziona con entrambi i tipi di token:
- token "Instagram Login" (iniziano con IG…)  → graph.instagram.com
- token Facebook / accesso unificato (EA…)   → graph.facebook.com
Il tipo viene rilevato da solo alla connessione.

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
"""
from __future__ import annotations

import time

import requests

IG_HOST = "https://graph.instagram.com"
FB_HOST = "https://graph.facebook.com"


class ErroreInstagram(RuntimeError):
    pass


def _chiama(host: str, version: str, metodo: str, path: str, token: str, **params) -> dict:
    params["access_token"] = token
    url = f"{host}/{version}/{path}"
    for tentativo in range(4):
        r = requests.request(metodo, url, data=params if metodo == "POST" else None,
                             params=params if metodo == "GET" else None, timeout=60)
        if r.status_code < 500:
            break
        time.sleep(5 * (tentativo + 1))
    data = r.json() if r.content else {}
    if not r.ok or "error" in data:
        raise ErroreInstagram(f"{metodo} {path}: {r.status_code} {data.get('error', r.text)}")
    return data


class Instagram:
    def __init__(self, token: str, user_id: str | None = None, version: str = "v23.0"):
        self.token = token
        self.v = version
        self.host, self.user_id, self.username = self._connetti(user_id)
        print(f"Connesso a @{self.username or '?'} (id {self.user_id}) via {self.host}")

    def _req(self, metodo: str, path: str, **params) -> dict:
        return _chiama(self.host, self.v, metodo, path, self.token, **params)

    def _connetti(self, user_id: str | None) -> tuple[str, str, str | None]:
        errori = []
        # 1) Token Instagram Login
        try:
            me = _chiama(IG_HOST, self.v, "GET", "me", self.token, fields="user_id,username")
            return IG_HOST, user_id or me["user_id"], me.get("username")
        except ErroreInstagram as e:
            errori.append(f"graph.instagram.com → {e}")

        # 2) Token Facebook / accesso unificato
        def fb(path, **p):
            return _chiama(FB_HOST, self.v, "GET", path, self.token, **p)

        try:
            if user_id:
                try:
                    info = fb(user_id, fields="id,username")
                    return FB_HOST, info["id"], info.get("username")
                except ErroreInstagram as e:
                    errori.append(f"graph.facebook.com /{user_id} → {e} (provo senza IG_USER_ID)")
            try:  # token legato direttamente all'account Instagram
                me = fb("me", fields="id,username")
                if me.get("username"):
                    return FB_HOST, me["id"], me["username"]
            except ErroreInstagram as e:
                errori.append(f"graph.facebook.com /me → {e}")

            # Gli account a cui il token dà accesso sono elencati nei granular_scopes.
            try:
                info = fb("debug_token", input_token=self.token).get("data", {})
                print(f"Token Facebook: tipo={info.get('type')} app={info.get('application')} "
                      f"scade={info.get('expires_at')} permessi={info.get('scopes')}")
                for g in info.get("granular_scopes", []):
                    print(f"  {g.get('scope')}: {g.get('target_ids', 'tutti')}")
                    if "instagram" in g.get("scope", "") and "publish" in g.get("scope", ""):
                        for tid in g.get("target_ids", []):
                            try:
                                ig = fb(tid, fields="id,username")
                                return FB_HOST, ig["id"], ig.get("username")
                            except ErroreInstagram as e:
                                errori.append(f"graph.facebook.com /{tid} → {e}")
            except ErroreInstagram as e:
                errori.append(f"graph.facebook.com debug_token → {e}")

            pagine = fb("me/accounts", fields="name,instagram_business_account{id,username}")
            print(f"Pagine Facebook visibili: {[p.get('name') for p in pagine.get('data', [])]}")
            for pagina in pagine.get("data", []):
                ig = pagina.get("instagram_business_account")
                if ig:
                    return FB_HOST, ig["id"], ig.get("username")
            errori.append("graph.facebook.com → token valido ma nessun account Instagram collegato")
        except ErroreInstagram as e:
            errori.append(f"graph.facebook.com → {e}")

        raise ErroreInstagram("Token non accettato:\n  " + "\n  ".join(errori))

    def _attendi(self, container_id: str, timeout: int = 600) -> None:
        fine = time.time() + timeout
        while time.time() < fine:
            stato = self._req("GET", container_id, fields="status_code,status")
            codice = stato.get("status_code")
            if codice == "FINISHED":
                return
            if codice in ("ERROR", "EXPIRED"):
                raise ErroreInstagram(f"Container {container_id}: {stato}")
            time.sleep(10)
        raise ErroreInstagram(f"Container {container_id} non pronto dopo {timeout}s")

    def _pubblica(self, **params) -> str:
        container = self._req("POST", f"{self.user_id}/media", **params)["id"]
        self._attendi(container)
        return self._req("POST", f"{self.user_id}/media_publish", creation_id=container)["id"]

    def post(self, image_url: str, caption: str) -> str:
        return self._pubblica(image_url=image_url, caption=caption)

    def storia(self, image_url: str) -> str:
        return self._pubblica(media_type="STORIES", image_url=image_url)

    def reel(self, video_url: str, caption: str, share_to_feed: bool = False) -> str:
        return self._pubblica(media_type="REELS", video_url=video_url, caption=caption,
                              share_to_feed="true" if share_to_feed else "false",
                              thumb_offset="4000")


def rinnova_token(token: str, version: str = "v23.0", app_id: str | None = None,
                  app_secret: str | None = None) -> dict | None:
    """Restituisce {access_token, expires_in?} oppure None se il token non va rinnovato."""
    r = requests.get(f"{IG_HOST}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    data = r.json()
    if r.ok and "access_token" in data:
        return data
    errore_ig = data

    # Token Facebook: se non scade (es. utente di sistema) non c'è niente da fare.
    try:
        info = _chiama(FB_HOST, version, "GET", "debug_token", token, input_token=token)["data"]
        if info.get("expires_at", 0) == 0:
            print("Token Facebook senza scadenza: nessun rinnovo necessario.")
            return None
    except ErroreInstagram:
        pass
    if app_id and app_secret:
        r = requests.get(f"{FB_HOST}/{version}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": app_secret, "fb_exchange_token": token}, timeout=60)
        data = r.json()
        if r.ok and "access_token" in data:
            return data
        raise ErroreInstagram(f"Rinnovo token Facebook fallito: {data}")
    if not token.startswith("IG"):
        print("Token Facebook/di sistema senza credenziali dell'app: nessun rinnovo "
              "(i token dell'utente di sistema non scadono).")
        return None
    raise ErroreInstagram(f"Rinnovo token fallito: {errore_ig}. Se è un token Facebook, "
                          "aggiungi i secrets FB_APP_ID e FB_APP_SECRET.")
