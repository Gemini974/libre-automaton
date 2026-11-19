#!/usr/bin/env python3
"""topstep-trader market data via OpenBB (provider yfinance, free, ~10-20 min delayed
for futures). Prints levels in Reunion time for plan.py.

  python3 market.py levels MBT            # last, previous day H/L, today's H/L, ATR(14) 15m
  python3 market.py orb MNQ --session ny  # opening range of a session (asia, london, comex, nymex, ny)
  python3 market.py spread                # MBT vs BTC spot

Needs: pip install openbb-core openbb-yfinance openbb-equity openbb-crypto
and network access to query1/query2.finance.yahoo.com and fc.yahoo.com.
"""
import argparse
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from plan import LOCAL, SESSIONS, local

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
# Topstep symbol -> Yahoo symbol (micro and full contracts quote the same price)
YAHOO = {
    "MNQ": "NQ=F", "NQ": "NQ=F", "MES": "ES=F", "ES": "ES=F", "MYM": "YM=F",
    "M2K": "RTY=F", "MGC": "GC=F", "GC": "GC=F", "SIL": "SI=F", "MCL": "CL=F",
    "CL": "CL=F", "M6E": "6E=F", "MBT": "BTC=F", "MET": "ETH=F", "BTC": "BTC-USD",
}
SESSION_KEYS = {"asia": 0, "london": 1, "comex": 2, "nymex": 3, "ny": 4}


def bars(sym, interval="15m", days=5):
    from openbb import obb  # imported late so --help works without OpenBB
    y = YAHOO.get(sym.upper(), sym)
    start = (datetime.now(UTC) - timedelta(days=days)).date().isoformat()
    if y.endswith("-USD"):
        df = obb.crypto.price.historical(y, provider="yfinance", interval=interval, start_date=start).to_df()
        tz = UTC
    else:
        df = obb.equity.price.historical(y, provider="yfinance", interval=interval, start_date=start).to_df()
        tz = NY
    idx = df.index if getattr(df.index, "tz", None) else df.index.tz_localize(tz)
    df.index = idx.tz_convert(LOCAL)
    return y, df


def atr(df, n=14):
    tr = []
    prev = None
    for _, r in df.iterrows():
        tr.append(r.high - r.low if prev is None else max(r.high - r.low, abs(r.high - prev), abs(r.low - prev)))
        prev = r.close
    tail = tr[-n:]
    return sum(tail) / len(tail)


def cmd_levels(a):
    y, df = bars(a.symbol)
    last = df.iloc[-1]
    today = df.index[-1].date()
    t = df[df.index.date == today]
    p = df[df.index.date < today]
    pd_ = p[p.index.date == p.index[-1].date()] if len(p) else p
    print(f"{a.symbol.upper()} ({y}), dernière bougie 15m {df.index[-1]:%d/%m %H:%M} (La Réunion), données retardées")
    print(f"  Dernier       {last.close:.2f}")
    print(f"  Aujourd'hui   haut {t.high.max():.2f}  bas {t.low.min():.2f}")
    if len(pd_):
        print(f"  Veille        haut {pd_.high.max():.2f}  bas {pd_.low.min():.2f}  clôture {pd_.close.iloc[-1]:.2f}")
    print(f"  5 jours       haut {df.high.max():.2f}  bas {df.low.min():.2f}")
    print(f"  ATR 14 (15m)  {atr(df):.2f} : un stop plus serré que ~1 ATR sera souvent touché par le bruit")


def cmd_orb(a):
    name, zone, t0, minutes = SESSIONS[SESSION_KEYS[a.session]]
    y, df = bars(a.symbol, interval="5m", days=3)
    day = df.index[-1].date() if not a.date else datetime.fromisoformat(a.date).date()
    for d in (day, day - timedelta(days=1)):
        o = local(d, zone, t0)
        rng = df[(df.index >= o) & (df.index < o + timedelta(minutes=minutes))]
        if len(rng):
            break
    else:
        sys.exit(f"Pas de bougies pour le range {name} (session pas encore ouverte ou données absentes).")
    hi, lo = rng.high.max(), rng.low.min()
    print(f"{a.symbol.upper()} ({y}) range d'ouverture {name} {o:%d/%m %H:%M}-{o + timedelta(minutes=minutes):%H:%M} (La Réunion)")
    print(f"  Haut {hi:.2f}  Bas {lo:.2f}  Milieu {(hi + lo) / 2:.2f}  ({len(rng)} bougies 5m)")
    after = df[df.index >= o + timedelta(minutes=minutes)]
    trig = None
    for ts, r in after.iterrows():
        if r.close > hi:
            trig = ("ACHAT", ts, r.close)
            break
        if r.close < lo:
            trig = ("VENTE", ts, r.close)
            break
    if trig:
        print(f"  Déclenché : {trig[0]} à {trig[1]:%H:%M}, clôture 5m {trig[2]:.2f}")
    else:
        print(f"  En attente : aucune clôture 5m hors du range (dernier {df.close.iloc[-1]:.2f})")
    sides = ["long" if trig[0] == "ACHAT" else "short"] if trig else ["long", "short"]
    for side in sides:
        print(f"  plan.py : python3 plan.py plan --symbol {a.symbol.upper()} --side {side} --or-high {hi:.2f} --or-low {lo:.2f}")


def cmd_spread(a):
    _, f = bars("MBT", days=2)
    _, s = bars("BTC", days=2)
    j = f[["close"]].rename(columns={"close": "close_mbt"}).join(
        s[["close"]].rename(columns={"close": "close_spot"}), how="inner")
    if not len(j):
        sys.exit("Pas de bougie commune entre le MBT et le spot.")
    j = j.iloc[:-1]  # the last bar may still be forming on one of the two feeds
    if not len(j):
        sys.exit("Pas assez de bougies clôturées.")
    d = (j.close_mbt - j.close_spot).tail(4)
    r = j.iloc[-1]
    print(f"Écart MBT - spot (bougies 15m clôturées, jusqu'à {j.index[-1]:%d/%m %H:%M} La Réunion) : médiane {d.median():+.0f} points")
    print(f"  Dernière : MBT {r.close_mbt:.0f}  spot {r.close_spot:.0f}  ({r.close_mbt - r.close_spot:+.0f}). Vérifier dans TopstepX avant d'entrer.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("levels")
    l.add_argument("symbol")
    o = sub.add_parser("orb")
    o.add_argument("symbol")
    o.add_argument("--session", choices=list(SESSION_KEYS), default="ny")
    o.add_argument("--date")
    sub.add_parser("spread")
    a = p.parse_args()
    {"levels": cmd_levels, "orb": cmd_orb, "spread": cmd_spread}[a.cmd](a)


if __name__ == "__main__":
    main()
