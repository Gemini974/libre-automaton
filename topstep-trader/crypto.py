#!/usr/bin/env python3
"""topstep-trader crypto context from free public APIs (no key). Standard library only.

  python3 crypto.py onchain              # stablecoins (DefiLlama), difficulty, hashrate, fees (Mempool)
  python3 crypto.py derivs [btc|eth|gold|us500|us100|oil|silver]
                                         # funding, open interest, liquidation clusters, key levels (Swiftedge)
  python3 crypto.py sentiment            # Fear & Greed, 24h liquidations, long/short (MarginPad)
  python3 crypto.py flows [--days 7]     # ETF / corporate BTC and ETH buys and sells (CorpStacking)
  python3 crypto.py all

Hosts: stablecoins.llama.fi, mempool.space, swiftedge.uk, marginpad.io,
www.corpstacking.com, api.coingecko.com. Third-party data: say where it comes from.
"""
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Indian/Reunion")
UA = {"User-Agent": "Mozilla/5.0 (topstep-trader)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def safe(fn):
    def run(*a, **k):
        try:
            fn(*a, **k)
        except Exception as e:  # one source down must not hide the others
            print(f"  [indisponible : {type(e).__name__} {str(e)[:80]}]")
    return run


def usd(x, sign=False):
    s = "+" if sign and x > 0 else ""
    return f"{s}{x / 1e9:.1f} Md$" if abs(x) >= 1e9 else f"{s}{x / 1e6:.0f} M$"


def n(x):
    return f"{x:,.0f}".replace(",", " ")


@safe
def onchain(_a=None):
    print("ON-CHAIN")
    st = get("https://stablecoins.llama.fi/stablecoincharts/all")
    t = lambda r: r["totalCirculatingUSD"]["peggedUSD"]
    now, w, m = t(st[-1]), t(st[-8]), t(st[-31])
    print(f"  Stablecoins : {usd(now)} (7 j {usd(now - w, True)}, 30 j {usd(now - m, True)})  [DefiLlama]")
    d = get("https://mempool.space/api/v1/difficulty-adjustment")
    when = datetime.fromtimestamp(d["estimatedRetargetDate"] / 1000, LOCAL)
    print(f"  Prochain ajustement de difficulté : {d['difficultyChange']:+.1f} % vers le {when:%d/%m %Hh%M} (précédent {d['previousRetarget']:+.1f} %)  [Mempool]")
    h = get("https://mempool.space/api/v1/mining/hashrate/1m")
    print(f"  Puissance du réseau : {n(h['currentHashrate'] / 1e18)} EH/s")
    f = get("https://mempool.space/api/v1/fees/recommended")
    print(f"  Frais : {f['fastestFee']} sat/vB (rapide), {f['economyFee']} (éco). 1 = réseau calme, demande faible")


@safe
def derivs(a):
    m = getattr(a, "market", "btc") or "btc"
    print(f"DÉRIVÉS {m.upper()}  [Swiftedge, contrats perpétuels]")
    f = get(f"https://swiftedge.uk/api/v1/funding-and-open-interest?market={m}")
    oi = f.get("open_interest") or {}
    print(f"  Financement : {f.get('funding_rate_8h_pct', 0):+.4f} % / 8 h ({f.get('funding_annualized_pct', 0):+.1f} % par an). Négatif = vendeurs majoritaires")
    if oi:
        hist = [x["contracts"] for x in f.get("open_interest_history", [])]
        wk = f"{100 * (hist[-1] / hist[0] - 1):+.1f} % sur 7 j" if len(hist) > 1 else ""
        print(f"  Positions ouvertes : {usd(oi.get('usd', 0))} ({oi.get('change_4h_pct', 0):+.1f} % sur 4 h, {wk})")
    h = get(f"https://swiftedge.uk/api/v1/liquidation-heatmap?market={m}")
    print(f"  Prix {n(h['price_usd'])}. Liquidations à 5 % : vendeurs au-dessus {usd(h['shorts_above_within_5pct_usd'])}, acheteurs en dessous {usd(h['longs_below_within_5pct_usd'])}")
    for side, key in (("au-dessus (vendeurs)", "largest_short_clusters_above"), ("en dessous (acheteurs)", "largest_long_clusters_below")):
        cl = ", ".join(f"{n(c['price'])} ({usd(c['estimated_usd'])})" for c in h.get(key, [])[:3])
        print(f"  Amas de liquidations {side} : {cl}")
    k = get(f"https://swiftedge.uk/api/v1/key-levels?market={m}")
    for side in ("above", "below"):
        lv = "; ".join(f"{n(x['price'])} {x['level']}" for x in k.get(side, [])[:4])
        print(f"  Niveaux {'au-dessus' if side == 'above' else 'en dessous'} : {lv}")


@safe
def sentiment(_a=None):
    print("SENTIMENT  [MarginPad]")
    fg = get("https://marginpad.io/api/v1/fear-greed")["data"]["data"][:7]
    print("  Fear & Greed (7 j) : " + ", ".join(str(x["v"]) for x in fg) + f" ({fg[0]['c']})")
    lq = get("https://marginpad.io/api/v1/liquidations")["data"]
    mk = lq["market"]
    btc = next((c for c in lq["coins"] if c["s"] == "BTC"), None)
    print(f"  Liquidations 24 h, marché : {usd(mk['total'])} (acheteurs {usd(mk['long'])}, vendeurs {usd(mk['short'])})")
    if btc:
        print(f"  dont BTC : {usd(btc['liq'])} (acheteurs {usd(btc['long'])}, vendeurs {usd(btc['short'])})")
    ls = get("https://marginpad.io/api/v1/long-short")["data"]["coins"]
    for s in ("BTC", "ETH"):
        c = next((x for x in ls if x["s"] == s), None)
        if c:
            print(f"  {s} comptes acheteurs / vendeurs : {c['longPct']:.0f} % / {c['shortPct']:.0f} %")


@safe
def flows(a):
    days = getattr(a, "days", 7) or 7
    print(f"FLUX ETF ET ENTREPRISES, {days} derniers jours  [CorpStacking]")
    feed = get("https://www.corpstacking.com/feed.json")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    tot = {}
    rows = []
    for it in feed.get("items", []):
        dt = datetime.fromisoformat(it["date_published"].replace("Z", "+00:00"))
        if dt < since:
            continue
        m = re.search(r"\b(bought|sold|acquired|purchased)\s+([\d,\.]+)\s+(BTC|ETH)\b.*?\$([\d,\.]+)", it.get("title", ""))
        if not m:
            continue
        sign = -1 if m.group(1) == "sold" else 1
        coin, amount = m.group(3), float(m.group(4).replace(",", ""))
        tot.setdefault(coin, [0.0, 0.0])
        tot[coin][0 if sign > 0 else 1] += amount
        rows.append(f"  {dt:%d/%m} {it['title'][:95]}")
    for coin, (buy, sell) in tot.items():
        print(f"  {coin} : achats {usd(buy)}, ventes {usd(sell)}, net {usd(buy - sell, True)}")
    print("\n".join(rows[:8]) if rows else "  Aucun mouvement chiffré trouvé dans le flux.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("onchain")
    d = sub.add_parser("derivs")
    d.add_argument("market", nargs="?", default="btc")
    sub.add_parser("sentiment")
    f = sub.add_parser("flows")
    f.add_argument("--days", type=int, default=7)
    sub.add_parser("all")
    a = p.parse_args()
    print(f"Relevé du {datetime.now(LOCAL):%d/%m %H:%M} (La Réunion)")
    if a.cmd == "all":
        a.market, a.days = "btc", 7
        for fn in (onchain, derivs, sentiment, flows):
            fn(a)
            print()
    else:
        {"onchain": onchain, "derivs": derivs, "sentiment": sentiment, "flows": flows}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
