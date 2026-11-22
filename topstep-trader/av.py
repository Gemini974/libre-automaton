#!/usr/bin/env python3
"""topstep-trader news sentiment and US macro from Alpha Vantage (free key, 25 requests a day).
Standard library only. Answers are cached 6 hours to save the daily quota.

  python3 av.py news btc        # sentiment of the latest news on Bitcoin (1 request)
  python3 av.py news macro      # macro, monetary policy, markets (1 request)
  python3 av.py news energy     # energy and transport: oil (1 request)
  python3 av.py macro           # CPI, Fed funds, 2 and 10-year yields, unemployment (5 requests)

The key is read from the ALPHAVANTAGE_API_KEY environment variable (set it in the
environment's settings, never in the chat). --demo uses Alpha Vantage's demo key,
which only answers a few sample queries (tests).
Host: www.alphavantage.co
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "topstep-trader" / "av"
NEWS = {
    "btc": {"tickers": "CRYPTO:BTC"},
    "eth": {"tickers": "CRYPTO:ETH"},
    "macro": {"topics": "economy_macro,economy_monetary,financial_markets"},
    "energy": {"topics": "energy_transportation"},
    "fx": {"tickers": "FOREX:USD"},
    "aapl": {"tickers": "AAPL"},  # works with --demo
}


def call(params, key, max_age=6 * 3600):
    q = urllib.parse.urlencode({**params, "apikey": key})
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(urllib.parse.urlencode(params).encode()).hexdigest() + ".json")
    if f.exists() and time.time() - f.stat().st_mtime < max_age:
        return json.loads(f.read_text())
    req = urllib.request.Request(f"https://www.alphavantage.co/query?{q}", headers={"User-Agent": "topstep-trader"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    msg = data.get("Information") or data.get("Note") or data.get("Error Message")
    if msg:
        raise RuntimeError(msg[:160])
    f.write_text(json.dumps(data))
    return data


def label(x):
    return ("baissier" if x <= -0.35 else "plutôt baissier" if x <= -0.15 else
            "neutre" if x < 0.15 else "plutôt haussier" if x < 0.35 else "haussier")


def news(a, key):
    p = {"function": "NEWS_SENTIMENT", "sort": "LATEST", "limit": 50, **NEWS[a.subject]}
    feed = call(p, key).get("feed", [])
    tick = NEWS[a.subject].get("tickers", "").split(",")[0]
    num = den = 0.0
    for it in feed:
        for ts in it.get("ticker_sentiment", []):
            if tick and ts["ticker"] == tick:
                w = float(ts["relevance_score"])
                num += w * float(ts["ticker_sentiment_score"])
                den += w
        if not tick:
            num += float(it.get("overall_sentiment_score", 0))
            den += 1
    avg = num / den if den else 0.0
    print(f"SENTIMENT DES ACTUALITÉS : {a.subject.upper()}  [Alpha Vantage, {len(feed)} articles]")
    print(f"  Score moyen {avg:+.2f} : {label(avg)}  (de −1 baissier à +1 haussier)")
    for it in feed[:6]:
        t = it["time_published"]
        print(f"  {t[6:8]}/{t[4:6]} {t[9:11]}h {it['overall_sentiment_label']:16s} {it['source'][:18]:18s} {it['title'][:85]}")


def macro(a, key):
    print("MACRO AMÉRICAINE  [Alpha Vantage]")
    series = [("Inflation CPI (indice)", {"function": "CPI", "interval": "monthly"}),
              ("Taux de la Fed (%)", {"function": "FEDERAL_FUNDS_RATE", "interval": "monthly"}),
              ("Taux 2 ans (%)", {"function": "TREASURY_YIELD", "interval": "daily", "maturity": "2year"}),
              ("Taux 10 ans (%)", {"function": "TREASURY_YIELD", "interval": "daily", "maturity": "10year"}),
              ("Chômage (%)", {"function": "UNEMPLOYMENT"})]
    for name, p in series:
        try:
            d = call(p, key, max_age=24 * 3600)["data"]
            v0, v1 = float(d[0]["value"]), float(d[1]["value"])
            extra = f", sur 12 mois {100 * (v0 / float(d[12]['value']) - 1):+.1f} %" if p["function"] == "CPI" else ""
            print(f"  {name:24s} {v0:8.2f} au {d[0]['date']} (précédent {v1:.2f}{extra})")
        except Exception as e:
            print(f"  {name:24s} indisponible : {str(e)[:90]}")


def main():
    pa = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pa.add_argument("--demo", action="store_true", help="use the demo key (sample queries only)")
    sub = pa.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("news")
    n.add_argument("subject", choices=list(NEWS), default="btc", nargs="?")
    sub.add_parser("macro")
    a = pa.parse_args()
    key = "demo" if a.demo else os.environ.get("ALPHAVANTAGE_API_KEY")
    if not key:
        sys.exit("Clé absente : ajouter la variable ALPHAVANTAGE_API_KEY dans les réglages de l'environnement, puis ouvrir une nouvelle session.")
    try:
        {"news": news, "macro": macro}[a.cmd](a, key)
    except RuntimeError as e:
        sys.exit(f"Alpha Vantage a refusé : {e}")


if __name__ == "__main__":
    main()
