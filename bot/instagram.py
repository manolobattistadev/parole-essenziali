"""Instagram API (Instagram Login) — pubblicazione di post, storie e reel, rinnovo del token.

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
"""
from __future__ import annotations

import time

import requests

BASE = "https://graph.instagram.com"


class ErroreInstagram(RuntimeError):
    pass


class Instagram:
    def __init__(self, token: str, user_id: str | None = None, version: str = "v23.0"):
        self.token = token
        self.v = version
        self.user_id = user_id or self._me()

    def _req(self, metodo: str, path: str, **params) -> dict:
        params["access_token"] = self.token
        url = f"{BASE}/{self.v}/{path}"
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

    def _me(self) -> str:
        return self._req("GET", "me", fields="user_id,username")["user_id"]

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


def rinnova_token(token: str) -> dict:
    """Restituisce {access_token, expires_in}. Il token deve avere almeno 24 ore."""
    r = requests.get(f"{BASE}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    data = r.json()
    if not r.ok or "access_token" not in data:
        raise ErroreInstagram(f"Rinnovo token fallito: {data}")
    return data
