#!/usr/bin/env python3
"""Données en direct depuis TopstepX (API ProjectX), en LECTURE SEULE : bougies uniquement, aucun ordre.

Nécessite l'abonnement API ProjectX de l'utilisateur et deux variables d'environnement, saisies
par l'utilisateur dans les réglages de l'environnement (jamais dans la conversation) :
  PROJECTX_USERNAME   identifiant TopstepX
  PROJECTX_API_KEY    clé API ProjectX
et l'hôte api.topstepx.com autorisé dans le réseau de l'environnement.
Sans ces variables, market.bars() garde Yahoo (futures retardés d'environ 10 min).

  /opt/openbb/bin/python topstepx.py MGC 5m 1     # test : dernières bougies 5 min
"""
import os
import sys
from datetime import UTC, datetime, timedelta

API = "https://api.topstepx.com/api"
UNITS = {"1m": (2, 1), "5m": (2, 5), "15m": (2, 15), "30m": (2, 30), "1h": (3, 1), "4h": (3, 4), "1d": (4, 1)}
_TOKEN = {}


def available():
    return bool(os.environ.get("PROJECTX_USERNAME") and os.environ.get("PROJECTX_API_KEY"))


def _post(path, body, token=None):
    import requests
    h = {"Content-Type": "application/json", "accept": "text/plain"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = requests.post(API + path, json=body, headers=h, timeout=20)
    r.raise_for_status()
    js = r.json()
    if isinstance(js, dict) and js.get("success") is False:
        raise RuntimeError(f"{path} : erreur {js.get('errorCode')} {js.get('errorMessage') or ''}".strip())
    return js


def token():
    if "t" not in _TOKEN:  # jeton valable 24 h ; une connexion par lancement suffit
        _TOKEN["t"] = _post("/Auth/loginKey", {"userName": os.environ["PROJECTX_USERNAME"],
                                               "apiKey": os.environ["PROJECTX_API_KEY"]})["token"]
    return _TOKEN["t"]


def contract(sym):
    cs = _post("/Contract/search", {"searchText": sym, "live": False}, token()).get("contracts", [])
    cs = [c for c in cs if str(c.get("name", "")).upper().startswith(sym.upper())] or cs
    act = [c for c in cs if c.get("activeContract")] or cs
    if not act:
        raise RuntimeError(f"aucun contrat TopstepX pour {sym}")
    return act[0]


def bars(sym, interval="15m", days=5):
    """Même format que market.bars : (nom, DataFrame open/high/low/close/volume, index en heure de La Réunion)."""
    import pandas as pd
    unit, n = UNITS[interval]
    c = contract(sym)
    end = datetime.now(UTC)
    js = _post("/History/retrieveBars", {"contractId": c["id"], "live": False,
                                         "startTime": (end - timedelta(days=days)).isoformat(),
                                         "endTime": end.isoformat(), "unit": unit, "unitNumber": n,
                                         "limit": 20000, "includePartialBar": True}, token())
    b = js.get("bars", [])
    if not b:
        raise RuntimeError(f"aucune bougie TopstepX pour {c.get('name')}")
    df = pd.DataFrame(b).rename(columns={"t": "date", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date"), utc=True)).tz_convert("Indian/Reunion")
    df = df.sort_index()[["open", "high", "low", "close", "volume"]]
    return f"TopstepX {c.get('name')} (direct)", df


if __name__ == "__main__":
    if not available():
        print("PROJECTX_USERNAME et PROJECTX_API_KEY absents : ajouter la clé dans les réglages de l'environnement")
        sys.exit(1)
    name, df = bars(sys.argv[1].upper(), sys.argv[2] if len(sys.argv) > 2 else "5m", int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    print(name, len(df), "bougies ; dernière", f"{df.index[-1]:%d/%m %H:%M}", "(La Réunion)")
    print(df.tail(3))
