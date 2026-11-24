#!/usr/bin/env python3
"""topstep-trader : graphique en ticks (bougies de N ticks) à partir des ticks Dukascopy.

Dukascopy publie gratuitement les ticks de l'or au comptant (XAUUSD) heure par heure.
Ce sont des changements de cotation (bid/ask), pas les transactions du CME : une
bougie de 500 ticks ici n'est donc pas identique à la 500T de TopstepX, mais elle
se forme de la même façon (vite quand le marché est actif, lentement quand il est calme).
Le serveur limite fortement le débit : télécharger quelques heures à la fois.

  python3 ticks.py fetch --hours 12                 # télécharge les 12 dernières heures terminées
  /opt/openbb/bin/python ticks.py bars --n 500 --chart /chemin/or_500t.png
  /opt/openbb/bin/python ticks.py volume MGC --chart /chemin/or_volume.png   # sans Dukascopy

« volume » : bougies d'activité construites avec les bougies 1 minute du contrat à terme
(Yahoo, 7 jours) : chaque bougie se ferme quand le même nombre de contrats a été échangé.
C'est l'équivalent le plus proche des bougies en ticks de TopstepX (transactions du CME),
à la minute près.
"""
import argparse
import datetime as dt
import glob
import lzma
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np

CACHE = os.path.expanduser("~/.cache/topstep-trader/ticks")
TICK = 0.1  # tick MGC


def fetch(hours, symbol="XAUUSD"):
    os.makedirs(CACHE, exist_ok=True)
    t = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None) - dt.timedelta(hours=1)
    got, wait, tries = 0, 3, 0
    while got < hours:
        f = f"{CACHE}/{symbol}_{t:%Y%m%d%H}.bi5"
        if os.path.exists(f) or t.weekday() == 5:
            got += os.path.exists(f)
            t -= dt.timedelta(hours=1)
            continue
        u = f"https://datafeed.dukascopy.com/datafeed/{symbol}/{t.year}/{t.month - 1:02d}/{t.day:02d}/{t.hour:02d}h_ticks.bi5"
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
            open(f, "wb").write(b)
            print(f"  {t:%d/%m %Hh} UTC : {len(b)} octets", flush=True)
            got += 1
            t -= dt.timedelta(hours=1)
            wait, tries = 3, 0
        except urllib.error.HTTPError as e:
            if e.code == 404:
                t -= dt.timedelta(hours=1)
                continue
            tries += 1
            wait = min(120, wait * 2)
            print(f"  {t:%d/%m %Hh} : serveur occupé ({e.code}), nouvel essai dans {wait} s", flush=True)
            if tries >= 5:
                t -= dt.timedelta(hours=1)
                tries = 0
        except Exception:
            tries += 1
            wait = min(120, wait * 2)
        time.sleep(wait)


def load(symbol="XAUUSD"):
    """Ticks (heure UTC, prix moyen bid/ask) de tous les fichiers en cache."""
    ts, px = [], []
    for f in sorted(glob.glob(f"{CACHE}/{symbol}_*.bi5")):
        b = open(f, "rb").read()
        if not b:
            continue
        r = lzma.decompress(b)
        a = np.frombuffer(r, dtype=">i4").reshape(-1, 5)
        h0 = dt.datetime.strptime(os.path.basename(f)[len(symbol) + 1:-4], "%Y%m%d%H")
        ts.append(np.datetime64(h0) + a[:, 0].astype("timedelta64[ms]"))
        px.append((a[:, 1] + a[:, 2]) / 2000.0)
    if not ts:
        return None, None
    return np.concatenate(ts), np.concatenate(px)


def tick_bars(ts, px, n):
    import pandas as pd
    k = len(px) // n
    if k == 0:
        return None
    p = px[: k * n].reshape(k, n)
    t = ts[: k * n].reshape(k, n)
    df = pd.DataFrame({"open": p[:, 0], "high": p.max(1), "low": p.min(1), "close": p[:, -1],
                       "start": t[:, 0], "end": t[:, -1]})
    df.index = pd.to_datetime(df.end).dt.tz_localize("UTC").dt.tz_convert("Indian/Reunion")
    df["secs"] = (df.end - df.start).dt.total_seconds()
    return df


def volume_bars(m1, per_bar):
    import pandas as pd
    rows, acc, cur = [], 0.0, None
    for t, r in m1.iterrows():
        if cur is None:
            cur = {"open": r.open, "high": r.high, "low": r.low, "start": t}
        cur["high"] = max(cur["high"], r.high)
        cur["low"] = min(cur["low"], r.low)
        acc += r.volume
        if acc >= per_bar:
            cur.update(close=r.close, end=t, volume=acc)
            rows.append(cur)
            cur, acc = None, 0.0
    df = pd.DataFrame(rows).set_index("end")
    df["secs"] = (df.index - df.start).dt.total_seconds() + 60
    return df


def cmd_volume(a):
    from market import bars
    from plan import SPECS
    from candles import describe, patterns
    sym = a.symbol.upper()
    tick = SPECS.get(sym, (0.01, 1))[0]
    _, m1 = bars(sym, "1m", 6)
    m1 = m1[m1.volume > 0]
    per = a.per_bar or float(m1.volume.resample("5min").sum().replace(0, np.nan).dropna().median())
    df = volume_bars(m1, per)
    d, sens = patterns(df[["open", "high", "low", "close"]])
    print(f"{sym} bougies d'activité de {per:.0f} contrats du contrat standard (volume Yahoo 1 min, retard ~10 min) : {len(df)} bougies, "
          f"durée médiane {df.secs.median() / 60:.0f} min ; ATR {d.atr.iloc[-1] / tick:.0f} ticks")
    print("  Une bougie courte = marché actif ; une bougie longue = marché calme.")
    for t, r in d.tail(a.last).iterrows():
        figs = [k for k in sens if r[k]]
        print(f"  {t:%d/%m %H:%M} ({df.secs[t] / 60:4.0f} min)  C {r.close:.2f}  {describe(r, tick)}" + (f"  [{', '.join(figs)}]" if figs else ""))
    if a.chart:
        draw(df.tail(150), a.chart, f"{sym} bougies de {per:.0f} contrats (La Réunion)")
        print(f"Graphique : {a.chart}")
    return 0


def draw(x, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 9), dpi=150)
    fig.patch.set_facecolor("#131722")
    ax.set_facecolor("#131722")
    for i, (_, r) in enumerate(x.iterrows()):
        c = "#26a69a" if r.close >= r.open else "#ef5350"
        ax.plot([i, i], [r.low, r.high], color=c, lw=0.8)
        ax.add_patch(plt.Rectangle((i - 0.35, min(r.open, r.close)), 0.7, max(abs(r.close - r.open), 1e-9), color=c))
    step = max(1, len(x) // 6)
    ax.set_xticks(range(0, len(x), step))
    ax.set_xticklabels([t.strftime("%d %Hh%M") for t in x.index[::step]], color="#aaa", fontsize=7)
    ax.tick_params(colors="#aaa", labelsize=7)
    ax.set_title(title, color="white", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--hours", type=int, default=12)
    b = sub.add_parser("bars")
    b.add_argument("--n", type=int, default=500)
    b.add_argument("--last", type=int, default=12, help="bougies décrites")
    b.add_argument("--chart")
    v = sub.add_parser("volume")
    v.add_argument("symbol")
    v.add_argument("--per-bar", type=float, help="contrats par bougie (défaut : volume médian de 5 min en séance)")
    v.add_argument("--last", type=int, default=12)
    v.add_argument("--chart")
    a = p.parse_args()
    if a.cmd == "volume":
        return cmd_volume(a)
    if a.cmd == "fetch":
        fetch(a.hours)
        return 0
    ts, px = load()
    if ts is None:
        print("aucun tick en cache : lancer d'abord ticks.py fetch")
        return 1
    df = tick_bars(ts, px, a.n)
    from candles import describe, patterns
    d, sens = patterns(df[["open", "high", "low", "close"]])
    print(f"Or au comptant (Dukascopy), bougies de {a.n} ticks : {len(df)} bougies du {df.index[0]:%d/%m %H:%M} au {df.index[-1]:%d/%m %H:%M} (La Réunion)")
    print(f"Durée médiane d'une bougie : {df.secs.median() / 60:.1f} min ; ATR {d.atr.iloc[-1] / TICK:.0f} ticks MGC")
    for t, r in d.tail(a.last).iterrows():
        figs = [k for k in sens if r[k]]
        print(f"  {t:%d/%m %H:%M} ({df.secs[t] / 60:4.1f} min)  C {r.close:.2f}  {describe(r, TICK)}" + (f"  [{', '.join(figs)}]" if figs else ""))
    if a.chart:
        draw(df.tail(150), a.chart, f"Or {a.n} ticks (Dukascopy, La Réunion)")
        print(f"Graphique : {a.chart}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
